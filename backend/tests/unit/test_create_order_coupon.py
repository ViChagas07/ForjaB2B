"""Integracao do cupom no CreateOrder (sem banco, repositorio fake)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.modules.ordering.application.errors import CouponNotApplicableError
from app.modules.ordering.application.order import CreateOrder
from app.modules.ordering.application.ports import (
    CouponForCheckout,
    OrderItemInput,
    OrderItemView,
    OrderView,
    ProductForOrder,
    RecoveryOfferView,
)
from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponRejectionReason,
    CouponType,
)
from app.modules.ordering.domain.payment import PaymentMethod

_COMPANY = uuid.UUID("88880000-0000-4000-8000-000000008001")
_USER = uuid.UUID("88880000-0000-4000-8000-000000008002")
_PRODUCT = uuid.UUID("88880000-0000-4000-8000-000000008003")
_CATEGORY = uuid.UUID("88880000-0000-4000-8000-000000008004")
_OFFER = uuid.UUID("88880000-0000-4000-8000-000000008005")
_OTHER_COMPANY = uuid.UUID("88880000-0000-4000-8000-000000008006")


def _product() -> ProductForOrder:
    return ProductForOrder(
        id=_PRODUCT,
        sku="COUPON-1",
        name="Produto Cupom",
        status="ACTIVE",
        is_epi=False,
        ca_valid_until=None,
        category_id=_CATEGORY,
        base_unit_price=Decimal("100.00"),
        min_order_qty=1,
        weight_kg=Decimal("2.0"),
        tiers=[],
        company_rules=[],
    )


def _coupon(
    *, coupon_type: CouponType = CouponType.PRODUCT_TOTAL, percent: str = "10.00"
) -> Coupon:
    return Coupon(
        code="CUPOM10",
        type=coupon_type,
        percent=Decimal(percent),
    )


class FakeRepository:
    def __init__(
        self,
        *,
        coupon: Coupon | None,
        offer: RecoveryOfferView | None = None,
        total_uses: int = 0,
        company_uses: int = 0,
    ) -> None:
        self.coupon = coupon
        self.offer = offer
        self.total_uses = total_uses
        self.company_uses = company_uses
        self.offer_lookups = 0
        self.created: dict[str, object] | None = None

    async def get_product_for_order(
        self, company_id: uuid.UUID, product_id: uuid.UUID, locale: str
    ) -> ProductForOrder | None:
        return _product() if product_id == _PRODUCT else None

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
        self.offer_lookups += 1
        return self.offer

    async def create_order(self, **kwargs: object) -> OrderView:
        self.created = kwargs
        items = kwargs["items"]
        assert isinstance(items, list)
        return OrderView(
            id=uuid.uuid4(),
            company_id=_COMPANY,
            status="RECEIVED",
            currency="BRL",
            subtotal=kwargs["subtotal"],
            discount_total=kwargs["discount_total"],
            shipping_total=kwargs["shipping_total"],
            tax_total=Decimal("0.00"),
            total=kwargs["total"],
            created_at=datetime.now(UTC),
            content_locale="pt-BR",
            coupon_code=kwargs.get("coupon_code"),
            items=[
                OrderItemView(
                    sku=item.sku,
                    product_name=item.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    base_unit_price=item.base_unit_price,
                    tier_min_quantity=item.tier_min_quantity,
                    line_total=item.line_total,
                    content_locale="pt-BR",
                )
                for item in items
            ],
        )


def _create(repository: FakeRepository) -> CreateOrder:
    return CreateOrder(repository=repository, today=datetime.now(UTC).date())


async def test_cupom_produto_desliga_recovery_e_envia_snapshot() -> None:
    repository = FakeRepository(
        coupon=_coupon(),
        offer=RecoveryOfferView(id=_OFFER, type="PERCENT_DISCOUNT", percent=Decimal("3.00")),
    )
    order = await _create(repository).create(
        company_id=_COMPANY,
        buyer_user_id=_USER,
        items=[OrderItemInput(product_id=_PRODUCT, quantity=1)],
        payment_method=PaymentMethod.PIX,
        idempotency_key="coupon-product",
        coupon_code="  cupom10  ",
    )
    assert repository.offer_lookups == 0
    assert repository.created is not None
    assert repository.created["coupon_code"] == "CUPOM10"
    assert repository.created["discount_total"] == Decimal("0.00")
    assert repository.created["shipping_total"] == Decimal("25.00")
    assert repository.created["total"] == Decimal("115.00")
    assert repository.created["recovery_offer_id"] is None
    assert order.total == Decimal("115.00")


async def test_cupom_frete_acumula_com_recovery() -> None:
    repository = FakeRepository(
        coupon=_coupon(coupon_type=CouponType.SHIPPING),
        offer=RecoveryOfferView(id=_OFFER, type="PERCENT_DISCOUNT", percent=Decimal("3.00")),
    )
    order = await _create(repository).create(
        company_id=_COMPANY,
        buyer_user_id=_USER,
        items=[OrderItemInput(product_id=_PRODUCT, quantity=1)],
        payment_method=PaymentMethod.PIX,
        idempotency_key="coupon-shipping",
        coupon_code="CUPOM10",
    )
    assert repository.offer_lookups == 1
    assert repository.created is not None
    assert repository.created["discount_total"] == Decimal("3.00")
    assert repository.created["shipping_total"] == Decimal("25.00")
    assert repository.created["total"] == Decimal("119.50")
    assert repository.created["recovery_offer_id"] == _OFFER
    assert order.total == Decimal("119.50")


async def test_cupom_invalido_nao_cria_pedido() -> None:
    repository = FakeRepository(coupon=None)
    with pytest.raises(CouponNotApplicableError) as exc:
        await _create(repository).create(
            company_id=_COMPANY,
            buyer_user_id=_USER,
            items=[OrderItemInput(product_id=_PRODUCT, quantity=1)],
            payment_method=PaymentMethod.PIX,
            idempotency_key="coupon-invalid",
            coupon_code="NAO-EXISTE",
        )
    assert exc.value.reason is CouponRejectionReason.NOT_FOUND
    assert exc.value.code == "coupon_not_found"
    assert repository.created is None


async def test_cupom_de_outra_empresa_responde_not_found() -> None:
    restricted = Coupon(
        code="CUPOM10",
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("10.00"),
        restricted_company_id=_OTHER_COMPANY,
    )
    repository = FakeRepository(coupon=restricted)
    with pytest.raises(CouponNotApplicableError) as exc:
        await _create(repository).create(
            company_id=_COMPANY,
            buyer_user_id=_USER,
            items=[OrderItemInput(product_id=_PRODUCT, quantity=1)],
            payment_method=PaymentMethod.PIX,
            idempotency_key="coupon-other-company",
            coupon_code="CUPOM10",
        )
    assert exc.value.reason is CouponRejectionReason.NOT_FOUND
    assert exc.value.code == "coupon_not_found"
    assert repository.created is None


async def test_cupom_esgotado_nao_cria_pedido() -> None:
    # Limite 1 com uma contagem ja existente => esgotado.
    repository = FakeRepository(coupon=_coupon(), total_uses=1)
    repository.coupon = Coupon(
        code="CUPOM10",
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("10.00"),
        usage_limit_total=1,
    )
    with pytest.raises(CouponNotApplicableError) as exc:
        await _create(repository).create(
            company_id=_COMPANY,
            buyer_user_id=_USER,
            items=[OrderItemInput(product_id=_PRODUCT, quantity=1)],
            payment_method=PaymentMethod.PIX,
            idempotency_key="coupon-exhausted",
            coupon_code="CUPOM10",
        )
    assert exc.value.reason is CouponRejectionReason.EXHAUSTED
    assert repository.created is None
