"""Previa do cupom no checkout (sem persistencia).

Le o carrinho do proprio comprador, valida o cupom com as contagens atuais e
simula a MESMA ordem de calculo usada na criacao do pedido. Nada e gravado:
o resgate e a revalidacao atomica acontecem no CreateOrder.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.shipping import compute_shipping, compute_total_weight
from app.modules.ordering.application.errors import EmptyOrderError
from app.modules.ordering.application.ports import (
    CheckoutCartReader,
    OrderingRepository,
)
from app.modules.ordering.domain.checkout import calculate_recovery
from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponRejectionReason,
    CouponType,
    DiscountKind,
    OrderTotals,
    calculate_order_totals,
    evaluate_coupon_eligibility,
    is_valid_coupon_code,
    normalize_coupon_code,
)
from app.modules.ordering.domain.payment import PaymentMethod

_ZERO = Decimal("0.00")


@dataclass(frozen=True, kw_only=True)
class CouponPreviewResult:
    """Resultado da previa; ``valid=False`` traz o motivo tipado."""

    valid: bool
    reason: CouponRejectionReason | None = None
    missing_amount: Decimal | None = None
    subtotal: Decimal | None = None
    recovery_discount: Decimal | None = None
    coupon_discount: Decimal | None = None
    shipping_discount: Decimal | None = None
    shipping_total: Decimal | None = None
    pix_discount: Decimal | None = None
    total: Decimal | None = None
    applied_discounts: frozenset[DiscountKind] = frozenset()
    currency: str = "BRL"


class PreviewCoupon:
    """Caso de uso da previa do cupom no resumo do checkout."""

    def __init__(
        self,
        *,
        cart_reader: CheckoutCartReader,
        repository: OrderingRepository,
        pix_discount_rate: Decimal,
    ) -> None:
        self._cart_reader = cart_reader
        self._repository = repository
        self._pix_discount_rate = pix_discount_rate

    async def execute(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        code: str | None = None,
        payment_method: PaymentMethod = PaymentMethod.PIX,
        locale: str = "pt-BR",
    ) -> CouponPreviewResult:
        cart = await self._cart_reader.get_checkout_cart(company_id, user_id, locale)
        if cart is None or not cart.items:
            raise EmptyOrderError("O carrinho precisa ter ao menos um item.")

        coupon, invalid = await self._coupon_for_preview(
            code=code,
            company_id=company_id,
            subtotal=cart.subtotal,
        )
        if invalid is not None:
            return invalid

        shipping = compute_shipping(
            total_weight_kg=compute_total_weight(
                (item.quantity, item.weight_kg) for item in cart.items
            )
        )
        recovery_discount = _ZERO
        recovery_applied = False
        effective_shipping = shipping
        if coupon is None or coupon.type != CouponType.PRODUCT_TOTAL:
            offer = await self._repository.find_active_offer(company_id, user_id)
            if offer is not None:
                eligible_total = sum(
                    (item.line_total for item in cart.items if not item.is_negotiated),
                    _ZERO,
                )
                recovery = calculate_recovery(
                    offer_type=offer.type,
                    percent=offer.percent,
                    eligible_product_total=eligible_total,
                )
                recovery_discount = recovery.discount
                recovery_applied = recovery.free_shipping or recovery.discount > _ZERO
                if recovery.free_shipping:
                    effective_shipping = _ZERO

        totals = calculate_order_totals(
            subtotal=cart.subtotal,
            shipping=effective_shipping,
            coupon=coupon,
            recovery_discount=recovery_discount,
            pix_discount_rate=(
                self._pix_discount_rate if payment_method == PaymentMethod.PIX else None
            ),
        )
        return _valid(totals, effective_shipping, recovery_applied)

    async def _coupon_for_preview(
        self, *, code: str | None, company_id: uuid.UUID, subtotal: Decimal
    ) -> tuple[Coupon | None, CouponPreviewResult | None]:
        """Resolve o cupom ou devolve o resultado invalido tipado."""
        if code is None or not code.strip():
            return None, None
        normalized = normalize_coupon_code(code)
        if not is_valid_coupon_code(normalized):
            return None, _invalid(CouponRejectionReason.NOT_FOUND)
        coupon_view = await self._repository.get_coupon_for_checkout(normalized, company_id)
        if coupon_view is None:
            return None, _invalid(CouponRejectionReason.NOT_FOUND)
        eligibility = evaluate_coupon_eligibility(
            coupon=coupon_view.coupon,
            company_id=company_id,
            subtotal=subtotal,
            total_uses=coupon_view.total_uses,
            company_uses=coupon_view.company_uses,
            now=datetime.now(UTC),
        )
        if not eligibility.ok:
            return None, _invalid(eligibility.reason, eligibility.missing_amount)
        return coupon_view.coupon, None


def _invalid(
    reason: CouponRejectionReason | None, missing_amount: Decimal | None = None
) -> CouponPreviewResult:
    return CouponPreviewResult(
        valid=False,
        reason=reason,
        missing_amount=missing_amount,
    )


def _valid(
    totals: OrderTotals, effective_shipping: Decimal, recovery_applied: bool
) -> CouponPreviewResult:
    applied = set(totals.applied_discounts)
    if recovery_applied:
        applied.add(DiscountKind.RECOVERY)
    return CouponPreviewResult(
        valid=True,
        subtotal=totals.subtotal,
        recovery_discount=totals.recovery_discount,
        coupon_discount=totals.coupon_discount,
        shipping_discount=totals.shipping_discount,
        shipping_total=effective_shipping - totals.shipping_discount,
        pix_discount=totals.pix_discount,
        total=totals.total,
        applied_discounts=frozenset(applied),
    )
