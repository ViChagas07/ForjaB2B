"""Casos de uso do contexto de pedidos.

O pedido e criado como snapshot: precos sao recalculados no servidor a partir do
catalogo atual e preservados em ``order_items``. Nenhum preco/total/credito
enviado pelo cliente e confiado. Pedido faturado (boleto) reserva credito
atomicamente na MESMA transacao.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.core.metrics import increment_order_created
from app.domain.pricing import PriceSource, resolve_company_price
from app.domain.product_availability import is_sellable
from app.domain.shipping import compute_shipping, compute_total_weight
from app.modules.ordering.application.errors import (
    CouponNotApplicableError,
    EmptyOrderError,
    InvalidOrderStateError,
    OrderNotFoundError,
    ProductNotFoundError,
    ProductNotSellableError,
    QuantityBelowMinimumError,
)
from app.modules.ordering.application.ports import (
    OrderingRepository,
    OrderItemInput,
    OrderView,
    ResolvedItem,
)
from app.modules.ordering.domain.checkout import calculate_recovery
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
from app.modules.ordering.domain.payment import PaymentMethod


class CreateOrder:
    def __init__(self, *, repository: OrderingRepository, today: date | None = None) -> None:
        self._repository = repository
        self._today = today or date.today()

    async def create(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        items: list[OrderItemInput],
        payment_method: PaymentMethod,
        idempotency_key: str,
        po_number: str | None = None,
        notes: str | None = None,
        locale: str = "pt-BR",
        coupon_code: str | None = None,
    ) -> OrderView:
        if not items:
            raise EmptyOrderError()

        resolved: list[ResolvedItem] = []
        line_weights: list[tuple[int, Decimal | None]] = []
        for item in items:
            product = await self._repository.get_product_for_order(
                company_id, item.product_id, locale
            )
            if product is None:
                raise ProductNotFoundError()
            if not is_sellable(
                status=product.status,
                is_epi=product.is_epi,
                ca_valid_until=product.ca_valid_until,
                today=self._today,
            ):
                raise ProductNotSellableError()
            if item.quantity < product.min_order_qty:
                raise QuantityBelowMinimumError()

            price = resolve_company_price(
                base_unit_price=product.base_unit_price,
                tiers=product.tiers,
                quantity=item.quantity,
                category_id=product.category_id,
                rules=product.company_rules,
            )
            resolved.append(
                ResolvedItem(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    quantity=item.quantity,
                    unit_price=price.unit_price,
                    base_unit_price=product.base_unit_price,
                    tier_min_quantity=price.tier_min_quantity,
                    price_tier_id=price.tier_id,
                    line_total=price.unit_price * item.quantity,
                    is_negotiated=price.source == PriceSource.NEGOTIATED,
                )
            )
            line_weights.append((item.quantity, product.weight_kg))

        subtotal = sum((i.line_total for i in resolved), Decimal("0.00"))
        shipping_base = compute_shipping(total_weight_kg=compute_total_weight(line_weights))

        coupon = await self._resolve_coupon(
            company_id=company_id,
            subtotal=subtotal,
            coupon_code=coupon_code,
        )
        recovery_offer_id: uuid.UUID | None = None
        discount_total = Decimal("0.00")
        if coupon is None or coupon.type != CouponType.PRODUCT_TOTAL:
            discount_total, shipping_base, recovery_offer_id = await self._apply_recovery_offer(
                company_id=company_id,
                buyer_user_id=buyer_user_id,
                resolved=resolved,
                shipping_total=shipping_base,
            )

        shipping_total = shipping_base
        total = subtotal - discount_total + shipping_total
        if coupon is not None:
            totals = calculate_order_totals(
                subtotal=subtotal,
                shipping=shipping_base,
                coupon=coupon,
                recovery_discount=discount_total,
            )
            discount_total = totals.recovery_discount
            shipping_total = shipping_base - totals.shipping_discount
            total = totals.total

        return await self._repository.create_order(
            company_id=company_id,
            buyer_user_id=buyer_user_id,
            items=resolved,
            payment_method=payment_method.value,
            idempotency_key=idempotency_key,
            po_number=po_number,
            notes=notes,
            subtotal=subtotal,
            shipping_total=shipping_base,
            total=total,
            content_locale=locale,
            discount_total=discount_total,
            recovery_offer_id=recovery_offer_id,
            coupon_code=coupon.code if coupon is not None else None,
        )
        increment_order_created(payment_method.value)

    async def _resolve_coupon(
        self,
        *,
        company_id: uuid.UUID,
        subtotal: Decimal,
        coupon_code: str | None,
    ) -> Coupon | None:
        """Valida o cupom fora da transacao para compor o total esperado.

        O repositorio revalida sob lock na transacao; esta leitura serve para
        decidir a interacao com a recuperacao e calcular o total da requisicao.
        """
        if coupon_code is None:
            return None
        normalized = normalize_coupon_code(coupon_code)
        if not is_valid_coupon_code(normalized):
            raise CouponNotApplicableError(CouponRejectionReason.NOT_FOUND)
        view = await self._repository.get_coupon_for_checkout(normalized, company_id)
        if view is None:
            raise CouponNotApplicableError(CouponRejectionReason.NOT_FOUND)
        eligibility = evaluate_coupon_eligibility(
            coupon=view.coupon,
            company_id=company_id,
            subtotal=subtotal,
            total_uses=view.total_uses,
            company_uses=view.company_uses,
            now=datetime.now(UTC),
        )
        if not eligibility.ok:
            raise CouponNotApplicableError(
                eligibility.reason or CouponRejectionReason.NOT_FOUND,
                eligibility.missing_amount,
            )
        return view.coupon

    async def _apply_recovery_offer(
        self,
        *,
        company_id: uuid.UUID,
        buyer_user_id: uuid.UUID,
        resolved: list[ResolvedItem],
        shipping_total: Decimal,
    ) -> tuple[Decimal, Decimal, uuid.UUID | None]:
        """Oferta de recuperacao (FASE 4) resolvida pelo SERVIDOR.

        Nenhum token/valor vem do cliente: a oferta ativa e do carrinho do
        comprador. O resgate (uso unico) acontece na MESMA transacao do pedido,
        no repositorio.
        """
        offer = await self._repository.find_active_offer(company_id, buyer_user_id)
        if offer is None:
            return Decimal("0.00"), shipping_total, None
        eligible_total = sum(
            (i.line_total for i in resolved if not i.is_negotiated), Decimal("0.00")
        )
        recovery = calculate_recovery(
            offer_type=offer.type,
            percent=offer.percent,
            eligible_product_total=eligible_total,
        )
        effective_shipping = Decimal("0.00") if recovery.free_shipping else shipping_total
        return recovery.discount, effective_shipping, offer.id


class GetOrder:
    def __init__(self, *, repository: OrderingRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView:
        order = await self._repository.get_order(company_id, order_id)
        if order is None:
            raise OrderNotFoundError()
        return order


class CancelOrder:
    def __init__(self, *, repository: OrderingRepository) -> None:
        self._repository = repository

    async def cancel(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView:
        order = await self._repository.get_order(company_id, order_id)
        if order is None:
            raise OrderNotFoundError()
        if not can_cancel(OrderStatus(order.status)):
            raise InvalidOrderStateError()
        return await self._repository.cancel_order(company_id, order_id)
