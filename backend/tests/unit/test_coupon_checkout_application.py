"""Previa do cupom no checkout com carrinho/repositorio fake."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.ordering.application.coupon_checkout import PreviewCoupon
from app.modules.ordering.application.errors import EmptyOrderError
from app.modules.ordering.application.ports import (
    CheckoutCartItem,
    CheckoutCartSnapshot,
    CouponForCheckout,
    RecoveryOfferView,
)
from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponRejectionReason,
    CouponType,
    DiscountKind,
)
from app.modules.ordering.domain.payment import PaymentMethod

_NOW = datetime.now(UTC)
_COMPANY = uuid.UUID("99990000-0000-4000-8000-000000009001")
_USER = uuid.UUID("99990000-0000-4000-8000-000000009002")
_PRODUCT = uuid.UUID("99990000-0000-4000-8000-000000009003")


def _coupon(**changes: object) -> Coupon:
    base = Coupon(
        code="CUPOM10",
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("10.00"),
    )
    return replace(base, **changes)


class FakeCart:
    def __init__(self, *, items: list[CheckoutCartItem] | None = None, subtotal: str = "100.00"):
        self.items = items if items is not None else [_item()]
        self.subtotal = Decimal(subtotal)

    async def get_checkout_cart(
        self, company_id: uuid.UUID, user_id: uuid.UUID, locale: str = "pt-BR"
    ) -> CheckoutCartSnapshot:
        return CheckoutCartSnapshot(items=self.items, subtotal=self.subtotal)


class FakeRepository:
    def __init__(
        self,
        *,
        coupon: Coupon | None = None,
        total_uses: int = 0,
        company_uses: int = 0,
        offer: RecoveryOfferView | None = None,
    ) -> None:
        self.coupon = coupon
        self.total_uses = total_uses
        self.company_uses = company_uses
        self.offer = offer

    async def get_coupon_for_checkout(
        self, code: str, company_id: uuid.UUID
    ) -> CouponForCheckout | None:
        if self.coupon is None or self.coupon.code != code:
            return None
        return CouponForCheckout(
            coupon=self.coupon,
            total_uses=self.total_uses,
            company_uses=self.company_uses,
        )

    async def find_active_offer(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID
    ) -> RecoveryOfferView | None:
        return self.offer


def _item(*, is_negotiated: bool = False, line_total: str = "100.00") -> CheckoutCartItem:
    return CheckoutCartItem(
        product_id=_PRODUCT,
        quantity=1,
        unit_price=Decimal(line_total),
        line_total=Decimal(line_total),
        weight_kg=Decimal("2.0"),
        is_negotiated=is_negotiated,
    )


def _preview(
    *,
    coupon: Coupon | None,
    cart: FakeCart | None = None,
    offer: RecoveryOfferView | None = None,
    total_uses: int = 0,
    company_uses: int = 0,
    method: PaymentMethod = PaymentMethod.PIX,
) -> PreviewCoupon:
    return PreviewCoupon(
        cart_reader=cart or FakeCart(),
        repository=FakeRepository(
            coupon=coupon,
            total_uses=total_uses,
            company_uses=company_uses,
            offer=offer,
        ),
        pix_discount_rate=Decimal("0.05"),
    )


async def test_preview_sem_cupom_para_resumo_do_checkout() -> None:
    use_case = _preview(coupon=None)
    result = await use_case.execute(
        company_id=_COMPANY,
        user_id=_USER,
        code=None,
        payment_method=PaymentMethod.PIX,
    )
    assert result.valid is True
    assert result.reason is None
    assert result.subtotal == Decimal("100.00")
    assert result.shipping_total == Decimal("25.00")
    assert result.coupon_discount == Decimal("0.00")
    assert result.pix_discount == Decimal("6.25")
    assert result.total == Decimal("118.75")


async def test_preview_produto_com_pix() -> None:
    use_case = _preview(coupon=_coupon())
    result = await use_case.execute(
        company_id=_COMPANY,
        user_id=_USER,
        code=" cupom10 ",
        payment_method=PaymentMethod.PIX,
    )
    assert result.valid is True
    assert result.reason is None
    assert result.subtotal == Decimal("100.00")
    assert result.shipping_total == Decimal("25.00")
    assert result.coupon_discount == Decimal("10.00")
    assert result.shipping_discount == Decimal("0.00")
    assert result.pix_discount == Decimal("5.75")
    assert result.total == Decimal("109.25")


async def test_preview_frete_com_pix() -> None:
    use_case = _preview(coupon=_coupon(type=CouponType.SHIPPING, percent=Decimal("10.00")))
    result = await use_case.execute(
        company_id=_COMPANY,
        user_id=_USER,
        code="CUPOM10",
        payment_method=PaymentMethod.PIX,
    )
    assert result.valid is True
    assert result.shipping_discount == Decimal("2.50")
    assert result.shipping_total == Decimal("22.50")
    assert result.pix_discount == Decimal("6.13")
    assert result.total == Decimal("116.37")


async def test_preview_sem_pix_para_cartao() -> None:
    use_case = _preview(coupon=_coupon())
    result = await use_case.execute(
        company_id=_COMPANY,
        user_id=_USER,
        code="CUPOM10",
        payment_method=PaymentMethod.CARD,
    )
    assert result.pix_discount == Decimal("0.00")
    assert result.total == Decimal("115.00")


async def test_preview_produto_desliga_frete_gratis() -> None:
    use_case = _preview(
        coupon=_coupon(),
        offer=RecoveryOfferView(id=uuid.uuid4(), type="FREE_SHIPPING", percent=None),
    )
    result = await use_case.execute(company_id=_COMPANY, user_id=_USER, code="CUPOM10")
    assert result.recovery_discount == Decimal("0.00")
    assert result.shipping_total == Decimal("25.00")


async def test_preview_frete_gratis_marca_recovery() -> None:
    use_case = _preview(
        coupon=_coupon(type=CouponType.SHIPPING, percent=Decimal("10.00")),
        offer=RecoveryOfferView(id=uuid.uuid4(), type="FREE_SHIPPING", percent=None),
    )
    result = await use_case.execute(company_id=_COMPANY, user_id=_USER, code="CUPOM10")
    assert result.recovery_discount == Decimal("0.00")
    assert result.shipping_total == Decimal("0.00")
    assert DiscountKind.RECOVERY in result.applied_discounts


async def test_preview_frete_permite_recuperacao() -> None:
    use_case = _preview(
        coupon=_coupon(type=CouponType.SHIPPING, percent=Decimal("10.00")),
        offer=RecoveryOfferView(id=uuid.uuid4(), type="PERCENT_DISCOUNT", percent=Decimal("3.00")),
    )
    result = await use_case.execute(company_id=_COMPANY, user_id=_USER, code="CUPOM10")
    assert result.recovery_discount == Decimal("3.00")
    assert result.shipping_discount == Decimal("2.50")


async def test_preview_inexistente() -> None:
    result = await _preview(coupon=None).execute(
        company_id=_COMPANY, user_id=_USER, code="NAO-EXISTE"
    )
    assert result.valid is False
    assert result.reason is CouponRejectionReason.NOT_FOUND
    assert result.total is None


async def test_preview_expirado() -> None:
    coupon = _coupon(valid_until=_NOW - timedelta(seconds=1))
    result = await _preview(coupon=coupon).execute(
        company_id=_COMPANY, user_id=_USER, code="CUPOM10"
    )
    assert result.valid is False
    assert result.reason is CouponRejectionReason.EXPIRED


async def test_preview_pedido_minimo_informa_faltante() -> None:
    coupon = _coupon(min_order_amount=Decimal("150.00"))
    result = await _preview(coupon=coupon).execute(
        company_id=_COMPANY, user_id=_USER, code="CUPOM10"
    )
    assert result.valid is False
    assert result.reason is CouponRejectionReason.MIN_ORDER_NOT_MET
    assert result.missing_amount == Decimal("50.00")


async def test_preview_carrinho_vazio_422() -> None:
    cart = FakeCart(items=[], subtotal="0.00")
    with pytest.raises(EmptyOrderError):
        await _preview(coupon=_coupon(), cart=cart).execute(
            company_id=_COMPANY, user_id=_USER, code="CUPOM10"
        )
