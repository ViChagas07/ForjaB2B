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
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.application.i18n import ProductTextTranslation, resolve_product_text
from app.application.ports.tenant import TenantContext
from app.domain.i18n import DEFAULT_LOCALE
from app.domain.ledger import LedgerEntry, exposure
from app.domain.pricing import PriceTier
from app.infrastructure.db.company_pricing import load_company_price_rules
from app.infrastructure.db.coupon_redemptions import release_coupon_redemption
from app.infrastructure.db.outbox import enqueue_notification
from app.infrastructure.db.translations import load_product_translations
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ordering.application.errors import (
    CouponNotApplicableError,
    CreditAccountNotFoundError,
    IdempotencyConflictError,
    InsufficientCreditError,
    InvalidOrderStateError,
    OrderNotFoundError,
)
from app.modules.ordering.application.ports import (
    CouponForCheckout,
    OrderItemView,
    OrderView,
    ProductForOrder,
    RecoveryOfferView,
    ResolvedItem,
)
from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponRejectionReason,
    CouponType,
    calculate_order_totals,
    evaluate_coupon_eligibility,
    is_valid_coupon_code,
    normalize_coupon_code,
)
from app.modules.ordering.domain.enums import OrderStatus
from app.modules.ordering.domain.order import can_cancel

_ORDERS_KEY_UNIQUE = "uq_orders_idempotency_key"

_GET_PRODUCT = text(
    "SELECT p.id, p.sku, p.name, p.description, p.status, p.is_epi, p.ca_valid_until, "
    "p.base_unit_price, p.min_order_qty, p.weight_kg, p.category_id, p.image_url, "
    "p.attributes, c.slug AS category_slug "
    "FROM products p JOIN categories c ON c.id = p.category_id WHERE p.id = :product_id"
)
_GET_TIERS = text(
    "SELECT id, min_quantity, max_quantity, unit_price FROM product_price_tiers "
    "WHERE product_id = :product_id ORDER BY min_quantity"
)
_SELECT_BY_KEY = text(
    "SELECT id FROM orders WHERE idempotency_key = :idempotency_key AND company_id = :company_id"
)
_LOCK_CREDIT = text(
    "SELECT credit_limit FROM credit_accounts WHERE company_id = :company_id FOR UPDATE"
)
_SELECT_ENTRIES = text(
    "SELECT entry_type, amount FROM credit_entries WHERE company_id = :company_id"
)
_INSERT_ORDER = text(
    "INSERT INTO orders (company_id, buyer_user_id, subtotal, discount_total, shipping_total, "
    "coupon_code, coupon_type, coupon_percent, coupon_discount_amount, "
    "shipping_discount_amount, total, idempotency_key, po_number, notes, content_locale) "
    "VALUES (:company_id, :buyer_user_id, :subtotal, :discount_total, :shipping_total, "
    ":coupon_code, :coupon_type, :coupon_percent, :coupon_discount_amount, "
    ":shipping_discount_amount, :total, :idempotency_key, :po_number, :notes, "
    ":content_locale) RETURNING id"
)
_SELECT_ACTIVE_OFFER = text(
    "SELECT o.id, o.type, o.percent FROM cart_recovery_offers o "
    "JOIN carts c ON c.id = o.cart_id "
    "WHERE o.company_id = :company_id AND c.company_id = :company_id "
    "  AND c.user_id = :buyer_user_id AND o.redeemed_at IS NULL AND o.expires_at > now() "
    "ORDER BY o.created_at DESC, o.id DESC LIMIT 1"
)
_REDEEM_OFFER = text(
    "UPDATE cart_recovery_offers SET redeemed_at = now() "
    "WHERE id = :offer_id AND company_id = :company_id AND redeemed_at IS NULL"
)
_SELECT_COUPON_BY_CODE = text(
    "SELECT id, code, type, percent, max_discount_amount, min_order_amount, valid_from, "
    "valid_until, usage_limit_total, usage_limit_per_company, restricted_company_id, "
    "is_active FROM coupons WHERE code = :code"
)
_SELECT_COUPON_USES = text(
    "SELECT total_uses, company_uses FROM app.coupon_usage_counts(:coupon_id, :company_id)"
)
_LOCK_COUPON = text("SELECT pg_advisory_xact_lock(hashtextextended(:code, 0))")
_INSERT_COUPON_REDEMPTION = text(
    "INSERT INTO coupon_redemptions (coupon_id, order_id, company_id, amount_discounted) "
    "VALUES (:coupon_id, :order_id, :company_id, :amount_discounted)"
)
_INSERT_ITEM = text(
    "INSERT INTO order_items (order_id, company_id, product_id, price_tier_id, sku, "
    "product_name, quantity, unit_price, base_unit_price, tier_min_quantity, "
    "line_total, content_locale) VALUES (:order_id, :company_id, :product_id, "
    ":price_tier_id, :sku, :product_name, :quantity, :unit_price, "
    ":base_unit_price, :tier_min_quantity, :line_total, :content_locale)"
)
_INSERT_CREDIT = text(
    "INSERT INTO credit_entries (credit_account_id, company_id, entry_type, amount, "
    "reference_type, reference_id, idempotency_key) "
    "VALUES (:company_id, :company_id, :entry_type, :amount, 'order', :order_id, :key)"
)
_SELECT_ORDER = text(
    "SELECT id, company_id, status, currency, subtotal, discount_total, "
    "shipping_total, tax_total, total, created_at, content_locale, coupon_code, "
    "coupon_type, coupon_percent, coupon_discount_amount, shipping_discount_amount "
    "FROM orders WHERE id = :order_id AND company_id = :company_id"
)
_SELECT_ORDER_ITEMS = text(
    "SELECT sku, product_name, quantity, unit_price, base_unit_price, tier_min_quantity, "
    "line_total, content_locale FROM order_items WHERE order_id = :order_id ORDER BY created_at, id"
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

    async def get_product_for_order(
        self, company_id: uuid.UUID, product_id: uuid.UUID, locale: str = DEFAULT_LOCALE
    ) -> ProductForOrder | None:
        # UoW com tenant: le produto/tiers (globais) e as regras da empresa (RLS).
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            product = (await uow.session.execute(_GET_PRODUCT, {"product_id": product_id})).first()
            tiers_rows = (await uow.session.execute(_GET_TIERS, {"product_id": product_id})).all()
            rules = await load_company_price_rules(uow.session, product_ids=[product_id])
            await uow.commit()
            if product is None:
                return None

            # Resolve traduÃ§Ã£o se nÃ£o for pt-BR
            name = product.name
            if locale != DEFAULT_LOCALE:
                translations = await load_product_translations(
                    uow.session, product_ids=[product_id], locales=[locale]
                )
                trans = translations.get((product_id, locale))
                if trans:
                    resolved = resolve_product_text(
                        source_name=product.name,
                        source_description=product.description,
                        source_attributes=product.attributes,
                        locale=locale,
                        translation=ProductTextTranslation(
                            name=trans.name,
                            description=trans.description,
                            attributes=trans.attributes,
                        ),
                    )
                    name = resolved.name.value or product.name

            return ProductForOrder(
                id=product.id,
                sku=product.sku,
                name=name,
                status=product.status,
                is_epi=product.is_epi,
                ca_valid_until=product.ca_valid_until,
                category_id=product.category_id,
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
                company_rules=rules.get(product_id, []),
            )

    async def find_active_offer(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID
    ) -> RecoveryOfferView | None:
        tenant = TenantContext(company_id=company_id, user_id=buyer_user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_ACTIVE_OFFER,
                    {"company_id": company_id, "buyer_user_id": buyer_user_id},
                )
            ).first()
            await uow.commit()
        if row is None:
            return None
        return RecoveryOfferView(id=row.id, type=row.type, percent=row.percent)

    async def get_coupon_for_checkout(
        self, code: str, company_id: uuid.UUID
    ) -> CouponForCheckout | None:
        normalized = normalize_coupon_code(code)
        if not is_valid_coupon_code(normalized):
            return None
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (await uow.session.execute(_SELECT_COUPON_BY_CODE, {"code": normalized})).first()
            if row is None:
                await uow.commit()
                return None
            uses = (
                await uow.session.execute(
                    _SELECT_COUPON_USES,
                    {"coupon_id": row.id, "company_id": company_id},
                )
            ).one()
            await uow.commit()
        return CouponForCheckout(
            coupon=_coupon_from_row(row),
            total_uses=int(uses.total_uses),
            company_uses=int(uses.company_uses),
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
        content_locale: str,
        discount_total: Decimal = Decimal("0.00"),
        recovery_offer_id: uuid.UUID | None = None,
        coupon_code: str | None = None,
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
                content_locale=content_locale,
                discount_total=discount_total,
                recovery_offer_id=recovery_offer_id,
                coupon_code=coupon_code,
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
        content_locale: str,
        discount_total: Decimal = Decimal("0.00"),
        recovery_offer_id: uuid.UUID | None = None,
        coupon_code: str | None = None,
    ) -> OrderView:
        tenant = TenantContext(company_id=company_id, user_id=buyer_user_id)
        async with self._uow_factory.begin(tenant) as uow:
            # Ordem de locks igual ao cancelamento: credito antes do cupom.
            if payment_method == "BOLETO":
                await uow.session.execute(_LOCK_CREDIT, {"company_id": company_id})
            (
                coupon_id,
                coupon,
                coupon_discount,
                shipping_discount,
                original_shipping,
                effective_discount,
                effective_total,
                effective_offer_id,
            ) = await self._apply_coupon_in_transaction(
                uow,
                company_id=company_id,
                subtotal=subtotal,
                shipping_total=shipping_total,
                discount_total=discount_total,
                total=total,
                recovery_offer_id=recovery_offer_id,
                coupon_code=coupon_code,
            )
            net_shipping = original_shipping - shipping_discount

            if payment_method == "BOLETO":
                await self._check_credit_available(
                    uow, company_id=company_id, amount=effective_total
                )

            if effective_offer_id is not None:
                # Uso unico: resgate DENTRO da transacao do pedido; corrida
                # (outro checkout resgatou antes) falha fechado.
                redeemed = await uow.session.execute(
                    _REDEEM_OFFER,
                    {"offer_id": effective_offer_id, "company_id": company_id},
                )
                if getattr(redeemed, "rowcount", 0) == 0:
                    raise InvalidOrderStateError()

            order_id = (
                await uow.session.execute(
                    _INSERT_ORDER,
                    {
                        "company_id": company_id,
                        "buyer_user_id": buyer_user_id,
                        "subtotal": subtotal,
                        "discount_total": effective_discount,
                        "shipping_total": net_shipping,
                        "coupon_code": coupon.code if coupon is not None else None,
                        "coupon_type": coupon.type.value if coupon is not None else None,
                        "coupon_percent": coupon.percent if coupon is not None else None,
                        "coupon_discount_amount": coupon_discount,
                        "shipping_discount_amount": shipping_discount,
                        "total": effective_total,
                        "idempotency_key": idempotency_key,
                        "po_number": po_number,
                        "notes": notes,
                        "content_locale": content_locale,
                    },
                )
            ).scalar_one()

            if coupon is not None and coupon_id is not None:
                await uow.session.execute(
                    _INSERT_COUPON_REDEMPTION,
                    {
                        "coupon_id": coupon_id,
                        "order_id": order_id,
                        "company_id": company_id,
                        "amount_discounted": coupon_discount + shipping_discount,
                    },
                )

            await self._insert_order_items(
                uow,
                order_id=order_id,
                company_id=company_id,
                items=items,
                content_locale=content_locale,
            )

            # Reserva de credito com reference_id = order_id (se boleto).
            if payment_method == "BOLETO":
                await uow.session.execute(
                    _INSERT_CREDIT,
                    {
                        "company_id": company_id,
                        "entry_type": "RESERVE",
                        "amount": effective_total,
                        "order_id": order_id,
                        "key": f"order:{idempotency_key}",
                    },
                )

            # Outbox: publica o evento de pedido criado na mesma transacao.
            await enqueue_notification(
                uow.session,
                company_id=company_id,
                event_type="order.created",
                aggregate_id=order_id,
                payload={
                    "currency": "BRL",
                    "subtotal": str(subtotal),
                    "discount_total": str(effective_discount),
                    "shipping_total": str(net_shipping),
                    "shipping_discount_amount": str(shipping_discount),
                    "coupon_code": coupon.code if coupon is not None else None,
                    "coupon_type": coupon.type.value if coupon is not None else None,
                    "coupon_percent": str(coupon.percent) if coupon is not None else None,
                    "coupon_discount_amount": str(coupon_discount),
                    "total": str(effective_total),
                },
            )

            await uow.commit()

        result = await self.get_order(company_id, order_id)
        if result is None:  # pragma: no cover - ordem acabou de ser criada
            raise CreditAccountNotFoundError()
        return result

    async def _insert_order_items(
        self,
        uow: Any,
        *,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        items: list[ResolvedItem],
        content_locale: str,
    ) -> None:
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
                    "content_locale": content_locale,
                },
            )

    async def _apply_coupon_in_transaction(
        self,
        uow: Any,
        *,
        company_id: uuid.UUID,
        subtotal: Decimal,
        shipping_total: Decimal,
        discount_total: Decimal,
        total: Decimal,
        recovery_offer_id: uuid.UUID | None,
        coupon_code: str | None,
    ) -> tuple[
        uuid.UUID | None,
        Coupon | None,
        Decimal,
        Decimal,
        Decimal,
        Decimal,
        Decimal,
        uuid.UUID | None,
    ]:
        """Bloqueia/revalida o cupom e recalcula os totais DENTRO da transacao."""
        if coupon_code is None:
            return (
                None,
                None,
                Decimal("0.00"),
                Decimal("0.00"),
                shipping_total,
                discount_total,
                total,
                recovery_offer_id,
            )
        normalized = normalize_coupon_code(coupon_code)
        if not is_valid_coupon_code(normalized):
            raise CouponNotApplicableError(CouponRejectionReason.NOT_FOUND)

        # Advisory lock por codigo: serializa resgates/liberacoes do mesmo cupom
        # sem exigir UPDATE na tabela global (runtime e somente leitura nela).
        await uow.session.execute(_LOCK_COUPON, {"code": normalized})
        row = (await uow.session.execute(_SELECT_COUPON_BY_CODE, {"code": normalized})).first()
        if row is None:
            raise CouponNotApplicableError(CouponRejectionReason.NOT_FOUND)
        uses = (
            await uow.session.execute(
                _SELECT_COUPON_USES,
                {"coupon_id": row.id, "company_id": company_id},
            )
        ).one()
        coupon = _coupon_from_row(row)
        eligibility = evaluate_coupon_eligibility(
            coupon=coupon,
            company_id=company_id,
            subtotal=subtotal,
            total_uses=int(uses.total_uses),
            company_uses=int(uses.company_uses),
            now=datetime.now(UTC),
        )
        if not eligibility.ok:
            raise CouponNotApplicableError(
                eligibility.reason or CouponRejectionReason.NOT_FOUND,
                eligibility.missing_amount,
            )

        effective_recovery = (
            Decimal("0.00") if coupon.type == CouponType.PRODUCT_TOTAL else discount_total
        )
        effective_offer_id = None if coupon.type == CouponType.PRODUCT_TOTAL else recovery_offer_id
        totals = calculate_order_totals(
            subtotal=subtotal,
            shipping=shipping_total,
            coupon=coupon,
            recovery_discount=effective_recovery,
        )
        return (
            row.id,
            coupon,
            totals.coupon_discount,
            totals.shipping_discount,
            shipping_total,
            totals.recovery_discount,
            totals.total,
            effective_offer_id,
        )

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
                await uow.session.execute(
                    _SELECT_BY_KEY,
                    {"idempotency_key": idempotency_key, "company_id": company_id},
                )
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
            content_locale=row.content_locale or DEFAULT_LOCALE,
            coupon_code=row.coupon_code,
            coupon_type=CouponType(row.coupon_type) if row.coupon_type else None,
            coupon_percent=row.coupon_percent,
            coupon_discount_amount=row.coupon_discount_amount,
            shipping_discount_amount=row.shipping_discount_amount,
            items=[
                OrderItemView(
                    sku=r.sku,
                    product_name=r.product_name,
                    quantity=r.quantity,
                    unit_price=r.unit_price,
                    base_unit_price=r.base_unit_price,
                    tier_min_quantity=r.tier_min_quantity,
                    line_total=r.line_total,
                    content_locale=r.content_locale or DEFAULT_LOCALE,
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
            await release_coupon_redemption(uow.session, company_id=company_id, order_id=order_id)
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


def _coupon_from_row(row: Any) -> Coupon:
    return Coupon(
        code=row.code,
        type=CouponType(row.type),
        percent=row.percent,
        max_discount_amount=row.max_discount_amount,
        min_order_amount=row.min_order_amount,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        usage_limit_total=row.usage_limit_total,
        usage_limit_per_company=row.usage_limit_per_company,
        restricted_company_id=row.restricted_company_id,
        is_active=row.is_active,
    )
