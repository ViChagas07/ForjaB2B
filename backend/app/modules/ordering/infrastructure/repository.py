"""Repositorio SQLAlchemy do contexto de pedidos (snapshot + credito atomico).

``create_order`` cria o pedido e os itens (snapshot) e, para pedido faturado
(boleto), reserva credito na MESMA transacao: a conta e bloqueada com FOR UPDATE,
o saldo e validado e o lancamento RESERVE e registrado. Isso garante que nunca
haja pedido faturado sem reserva, nem reserva sem pedido. Idempotencia via
``orders.idempotency_key`` (constraint unica) e ``credit_entries.idempotency_key``
prefixado com ``order:``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.domain.ledger import LedgerEntry, exposure
from app.domain.pricing import PriceTier
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ordering.application.errors import (
    CreditAccountNotFoundError,
    IdempotencyConflictError,
    InsufficientCreditError,
    InvalidOrderStateError,
    OrderNotFoundError,
)
from app.modules.ordering.application.ports import (
    OrderItemView,
    OrderView,
    ProductForOrder,
    ResolvedItem,
)
from app.modules.ordering.domain.enums import OrderStatus
from app.modules.ordering.domain.order import can_cancel

_ORDERS_KEY_UNIQUE = "uq_orders_idempotency_key"

_GET_PRODUCT = text(
    "SELECT id, sku, name, status, is_epi, ca_valid_until, base_unit_price, min_order_qty, "
    "weight_kg FROM products WHERE id = :product_id"
)
_GET_TIERS = text(
    "SELECT id, min_quantity, max_quantity, unit_price FROM product_price_tiers "
    "WHERE product_id = :product_id ORDER BY min_quantity"
)
_SELECT_BY_KEY = text("SELECT id FROM orders WHERE idempotency_key = :idempotency_key")
_LOCK_CREDIT = text(
    "SELECT credit_limit FROM credit_accounts WHERE company_id = :company_id FOR UPDATE"
)
_SELECT_ENTRIES = text(
    "SELECT entry_type, amount FROM credit_entries WHERE company_id = :company_id"
)
_INSERT_ORDER = text(
    "INSERT INTO orders (company_id, buyer_user_id, subtotal, shipping_total, total, "
    "idempotency_key, po_number, notes) VALUES (:company_id, :buyer_user_id, :subtotal, "
    ":shipping_total, :total, :idempotency_key, :po_number, :notes) RETURNING id"
)
_INSERT_ITEM = text(
    "INSERT INTO order_items (order_id, company_id, product_id, price_tier_id, sku, "
    "product_name, quantity, unit_price, base_unit_price, tier_min_quantity, line_total) "
    "VALUES (:order_id, :company_id, :product_id, :price_tier_id, :sku, :product_name, "
    ":quantity, :unit_price, :base_unit_price, :tier_min_quantity, :line_total)"
)
_INSERT_CREDIT = text(
    "INSERT INTO credit_entries (credit_account_id, company_id, entry_type, amount, "
    "reference_type, reference_id, idempotency_key) "
    "VALUES (:company_id, :company_id, :entry_type, :amount, 'order', :order_id, :key)"
)
_SELECT_ORDER = text(
    "SELECT id, company_id, status, currency, subtotal, discount_total, shipping_total, "
    "tax_total, total, created_at FROM orders WHERE id = :order_id AND company_id = :company_id"
)
_SELECT_ORDER_ITEMS = text(
    "SELECT sku, product_name, quantity, unit_price, base_unit_price, tier_min_quantity, "
    "line_total FROM order_items WHERE order_id = :order_id ORDER BY created_at, id"
)
_SELECT_RESERVE = text(
    "SELECT COALESCE(SUM(amount), 0) FROM credit_entries "
    "WHERE reference_type = 'order' AND reference_id = :order_id AND entry_type = 'RESERVE'"
)
_UPDATE_ORDER_STATUS = text(
    "UPDATE orders SET status = :status WHERE id = :order_id AND company_id = :company_id"
)


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    while current is not None:
        name = getattr(current, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        current = current.__cause__
    return ""


class SqlAlchemyOrderingRepository:
    """Implementacao da porta OrderingRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_product_for_order(self, product_id: uuid.UUID) -> ProductForOrder | None:
        async with self._uow_factory.begin() as uow:
            product = (await uow.session.execute(_GET_PRODUCT, {"product_id": product_id})).first()
            tiers_rows = (await uow.session.execute(_GET_TIERS, {"product_id": product_id})).all()
            await uow.commit()
            if product is None:
                return None
            return ProductForOrder(
                id=product.id,
                sku=product.sku,
                name=product.name,
                status=product.status,
                is_epi=product.is_epi,
                ca_valid_until=product.ca_valid_until,
                base_unit_price=product.base_unit_price,
                min_order_qty=product.min_order_qty,
                weight_kg=product.weight_kg,
                tiers=[
                    PriceTier(
                        tier_id=r.id,
                        min_quantity=r.min_quantity,
                        max_quantity=r.max_quantity,
                        unit_price=r.unit_price,
                    )
                    for r in tiers_rows
                ],
            )

    async def create_order(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        items: list[ResolvedItem],
        payment_method: str,
        idempotency_key: str,
        po_number: str | None,
        notes: str | None,
        subtotal: Decimal,
        shipping_total: Decimal,
        total: Decimal,
    ) -> OrderView:
        existing_id = await self._find_by_key(company_id, idempotency_key)
        if existing_id is not None:
            return await self._idempotent_or_conflict(existing_id, company_id, total)
        try:
            return await self._create_inner(
                company_id=company_id,
                buyer_user_id=buyer_user_id,
                items=items,
                payment_method=payment_method,
                idempotency_key=idempotency_key,
                po_number=po_number,
                notes=notes,
                subtotal=subtotal,
                shipping_total=shipping_total,
                total=total,
            )
        except Exception as exc:
            if _constraint_name(exc) == _ORDERS_KEY_UNIQUE:
                existing_id = await self._find_by_key(company_id, idempotency_key)
                if existing_id is not None:
                    return await self._idempotent_or_conflict(existing_id, company_id, total)
            raise

    async def _create_inner(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        items: list[ResolvedItem],
        payment_method: str,
        idempotency_key: str,
        po_number: str | None,
        notes: str | None,
        subtotal: Decimal,
        shipping_total: Decimal,
        total: Decimal,
    ) -> OrderView:
        tenant = TenantContext(company_id=company_id, user_id=buyer_user_id)
        async with self._uow_factory.begin(tenant) as uow:
            if payment_method == "BOLETO":
                await self._check_credit_available(uow, company_id=company_id, amount=total)

            order_id = (
                await uow.session.execute(
                    _INSERT_ORDER,
                    {
                        "company_id": company_id,
                        "buyer_user_id": buyer_user_id,
                        "subtotal": subtotal,
                        "shipping_total": shipping_total,
                        "total": total,
                        "idempotency_key": idempotency_key,
                        "po_number": po_number,
                        "notes": notes,
                    },
                )
            ).scalar_one()

            for item in items:
                await uow.session.execute(
                    _INSERT_ITEM,
                    {
                        "order_id": order_id,
                        "company_id": company_id,
                        "product_id": item.product_id,
                        "price_tier_id": item.price_tier_id,
                        "sku": item.sku,
                        "product_name": item.name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "base_unit_price": item.base_unit_price,
                        "tier_min_quantity": item.tier_min_quantity,
                        "line_total": item.line_total,
                    },
                )

            # Reserva de credito com reference_id = order_id (se boleto).
            if payment_method == "BOLETO":
                await uow.session.execute(
                    _INSERT_CREDIT,
                    {
                        "company_id": company_id,
                        "entry_type": "RESERVE",
                        "amount": total,
                        "order_id": order_id,
                        "key": f"order:{idempotency_key}",
                    },
                )

            await uow.commit()

        result = await self.get_order(company_id, order_id)
        if result is None:  # pragma: no cover - ordem acabou de ser criada
            raise CreditAccountNotFoundError()
        return result

    async def _check_credit_available(
        self, uow: Any, *, company_id: uuid.UUID, amount: Decimal
    ) -> None:
        account = (await uow.session.execute(_LOCK_CREDIT, {"company_id": company_id})).first()
        if account is None:
            raise CreditAccountNotFoundError()
        credit_limit = account[0]
        entries_rows = (
            await uow.session.execute(_SELECT_ENTRIES, {"company_id": company_id})
        ).all()
        entries = [LedgerEntry(entry_type=r.entry_type, amount=r.amount) for r in entries_rows]
        if credit_limit - exposure(entries) < amount:
            raise InsufficientCreditError()

    async def _find_by_key(self, company_id: uuid.UUID, idempotency_key: str) -> uuid.UUID | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(_SELECT_BY_KEY, {"idempotency_key": idempotency_key})
            ).first()
            await uow.commit()
            return row[0] if row is not None else None

    async def _idempotent_or_conflict(
        self, order_id: uuid.UUID, company_id: uuid.UUID, expected_total: Decimal
    ) -> OrderView:
        order = await self.get_order(company_id, order_id)
        if order is None:
            raise IdempotencyConflictError()
        if order.total != expected_total:
            raise IdempotencyConflictError()
        return order

    async def get_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_ORDER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            if row is None:
                await uow.commit()
                return None
            items_rows = (
                await uow.session.execute(_SELECT_ORDER_ITEMS, {"order_id": order_id})
            ).all()
            await uow.commit()

        return OrderView(
            id=row.id,
            company_id=row.company_id,
            status=row.status,
            currency=row.currency,
            subtotal=row.subtotal,
            discount_total=row.discount_total,
            shipping_total=row.shipping_total,
            tax_total=row.tax_total,
            total=row.total,
            created_at=row.created_at,
            items=[
                OrderItemView(
                    sku=r.sku,
                    product_name=r.product_name,
                    quantity=r.quantity,
                    unit_price=r.unit_price,
                    base_unit_price=r.base_unit_price,
                    tier_min_quantity=r.tier_min_quantity,
                    line_total=r.line_total,
                )
                for r in items_rows
            ],
        )

    async def cancel_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            # Serializa o cancelamento com a captura de fatura (que tambem
            # bloqueia a conta de credito). Isso impede que um pedido seja
            # cancelado e faturado ao mesmo tempo, o que liberaria a reserva
            # duas vezes. Sem conta (empresa so PIX) o SELECT nao trava nada.
            await uow.session.execute(_LOCK_CREDIT, {"company_id": company_id})

            order = (
                await uow.session.execute(
                    _SELECT_ORDER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            if order is None:
                await uow.commit()
                raise OrderNotFoundError()
            # Revalida o estado SOB O LOCK: fecha o TOCTOU entre o caso de uso
            # (que checa can_cancel) e a escrita aqui.
            if not can_cancel(OrderStatus(order.status)):
                raise InvalidOrderStateError()

            await uow.session.execute(
                _UPDATE_ORDER_STATUS,
                {"order_id": order_id, "company_id": company_id, "status": "CANCELLED"},
            )
            reserved = (
                await uow.session.execute(_SELECT_RESERVE, {"order_id": order_id})
            ).scalar_one()
            if reserved and Decimal(reserved) > 0:
                await uow.session.execute(
                    _INSERT_CREDIT,
                    {
                        "company_id": company_id,
                        "entry_type": "RELEASE",
                        "amount": Decimal(reserved),
                        "order_id": order_id,
                        "key": f"release:{order_id}",
                    },
                )
            await uow.commit()

        result = await self.get_order(company_id, order_id)
        if result is None:
            raise CreditAccountNotFoundError()  # pragma: no cover
        return result
