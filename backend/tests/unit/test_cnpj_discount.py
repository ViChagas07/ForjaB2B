"""Desconto automatico CNPJ: dominio, pedido e protecao contra adulteracao.

Cobre a regra pura (15% para qualquer quantidade e 30% a partir de 30 unidades
do MESMO produto), a composicao por linha e a interacao com cupom/recovery.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.domain.pricing import (
    CNPJ_STANDARD_DISCOUNT_PERCENT,
    CNPJ_VOLUME_DISCOUNT_PERCENT,
    CNPJ_VOLUME_MIN_QUANTITY,
    CnpjDiscountBand,
    resolve_cnpj_price,
)
from app.modules.cart.interface.schemas import AddItemRequest
from app.modules.ordering.application.order import CreateOrder
from app.modules.ordering.application.ports import (
    CouponForCheckout,
    OrderItemInput,
    OrderItemView,
    OrderView,
    ProductForOrder,
    RecoveryOfferView,
)
from app.modules.ordering.domain.coupon import Coupon, CouponType
from app.modules.ordering.domain.payment import PaymentMethod
from app.modules.ordering.interface.schemas import CreateOrderRequest
from app.modules.payment.application.payment import InitiatePayment
from app.modules.payment.application.ports import (
    GatewayInstruction,
    OrderForPayment,
    PaymentRepository,
    PaymentView,
)
from app.modules.payment.domain.enums import PaymentMethod as PaymentMethodPayment

_COMPANY = uuid.UUID("99990000-0000-4000-8000-000000009001")
_USER = uuid.UUID("99990000-0000-4000-8000-000000009002")
_PRODUCT_A = uuid.UUID("99990000-0000-4000-8000-000000009003")
_PRODUCT_B = uuid.UUID("99990000-0000-4000-8000-000000009004")
_CATEGORY = uuid.UUID("99990000-0000-4000-8000-000000009005")
_OFFER = uuid.UUID("99990000-0000-4000-8000-000000009006")


def _product(product_id: uuid.UUID, *, price: str = "100.00") -> ProductForOrder:
    return ProductForOrder(
        id=product_id,
        sku=f"CNPJ-{product_id.hex[-4:]}",
        name=f"Produto {product_id.hex[-4:]}",
        status="ACTIVE",
        is_epi=False,
        ca_valid_until=None,
        category_id=_CATEGORY,
        base_unit_price=Decimal(price),
        min_order_qty=1,
        weight_kg=None,
        tiers=[],
        company_rules=[],
    )


class FakeRepository:
    def __init__(
        self,
        *,
        account_type: str = "COMPANY",
        coupon: Coupon | None = None,
        offer: RecoveryOfferView | None = None,
    ) -> None:
        self.account_type = account_type
        self.coupon = coupon
        self.offer = offer
        self.created: dict[str, object] | None = None

    async def get_product_for_order(
        self, company_id: uuid.UUID, product_id: uuid.UUID, locale: str = "pt-BR"
    ) -> ProductForOrder | None:
        if product_id == _PRODUCT_A:
            return _product(_PRODUCT_A)
        if product_id == _PRODUCT_B:
            return _product(_PRODUCT_B)
        return None

    async def get_company_account_type(self, company_id: uuid.UUID) -> str:
        return self.account_type

    async def get_coupon_for_checkout(
        self, code: str, company_id: uuid.UUID
    ) -> CouponForCheckout | None:
        if self.coupon is None or self.coupon.code != code:
            return None
        return CouponForCheckout(coupon=self.coupon, total_uses=0, company_uses=0)

    async def find_active_offer(
        self, company_id: uuid.UUID, buyer_user_id: uuid.UUID
    ) -> RecoveryOfferView | None:
        return self.offer

    async def get_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView | None:
        return None

    async def cancel_order(self, company_id: uuid.UUID, order_id: uuid.UUID) -> OrderView:
        raise NotImplementedError

    async def create_order(self, **kwargs: Any) -> OrderView:
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
                    list_unit_price=item.list_unit_price,
                    cnpj_discount_percent=item.cnpj_discount_percent,
                    cnpj_discount_band=item.cnpj_discount_band,
                    tier_min_quantity=item.tier_min_quantity,
                    line_total=item.line_total,
                    content_locale="pt-BR",
                )
                for item in items
            ],
        )


async def _create(
    repository: FakeRepository,
    items: list[OrderItemInput],
    *,
    coupon_code: str | None = None,
) -> OrderView:
    return await CreateOrder(repository=repository).create(
        company_id=_COMPANY,
        buyer_user_id=_USER,
        items=items,
        payment_method=PaymentMethod.PIX,
        idempotency_key=f"cnpj-{uuid.uuid4()}",
        coupon_code=coupon_code,
    )


def test_constantes_centrais() -> None:
    assert Decimal("15") == CNPJ_STANDARD_DISCOUNT_PERCENT
    assert Decimal("30") == CNPJ_VOLUME_DISCOUNT_PERCENT
    assert CNPJ_VOLUME_MIN_QUANTITY == 30


def test_nao_cnpj_sem_desconto() -> None:
    price = resolve_cnpj_price(
        account_type="PERSON", quantity=30, list_unit_price=Decimal("100.00")
    )
    assert price.unit_price == Decimal("100.00")
    assert price.list_unit_price == Decimal("100.00")
    assert price.discount_percent == Decimal("0.00")
    assert price.discount_band is CnpjDiscountBand.NONE
    assert price.units_to_volume_discount is None


@pytest.mark.parametrize(
    ("quantity", "percent", "unit_price", "missing"),
    [
        (1, Decimal("15"), Decimal("85.00"), 29),
        (29, Decimal("15"), Decimal("85.00"), 1),
        (30, Decimal("30"), Decimal("70.00"), None),
        (31, Decimal("30"), Decimal("70.00"), None),
    ],
)
def test_faixas_cnpj(
    quantity: int,
    percent: Decimal,
    unit_price: Decimal,
    missing: int | None,
) -> None:
    price = resolve_cnpj_price(
        account_type="COMPANY", quantity=quantity, list_unit_price=Decimal("100.00")
    )
    assert price.discount_percent == percent
    assert price.unit_price == unit_price
    assert price.units_to_volume_discount == missing


def test_arredondamento_half_up_ao_centavo() -> None:
    # 24.90 * 0.85 = 21.165 -> 21.17
    price = resolve_cnpj_price(account_type="COMPANY", quantity=1, list_unit_price=Decimal("24.90"))
    assert price.unit_price == Decimal("21.17")
    # 0.05 * 0.70 = 0.035 -> 0.04
    volume = resolve_cnpj_price(
        account_type="COMPANY", quantity=30, list_unit_price=Decimal("0.05")
    )
    assert volume.unit_price == Decimal("0.04")


@pytest.mark.parametrize("quantity", [0, -1])
def test_quantidade_invalida_falha(quantity: int) -> None:
    with pytest.raises(ValueError):
        resolve_cnpj_price(
            account_type="COMPANY", quantity=quantity, list_unit_price=Decimal("10.00")
        )


@pytest.mark.parametrize("quantity", [1.5, True])
def test_quantidade_nao_inteira_falha(quantity: Any) -> None:
    with pytest.raises(TypeError):
        resolve_cnpj_price(
            account_type="COMPANY",
            quantity=quantity,
            list_unit_price=Decimal("10.00"),
        )


async def test_pedido_cnpj_1_unidade_aplica_15_e_snapshot() -> None:
    repository = FakeRepository()
    order = await _create(repository, [OrderItemInput(product_id=_PRODUCT_A, quantity=1)])

    assert order.subtotal == Decimal("85.00")
    assert order.total == Decimal("85.00")
    item = order.items[0]
    assert item.unit_price == Decimal("85.00")
    assert item.list_unit_price == Decimal("100.00")
    assert item.cnpj_discount_percent == Decimal("15")
    assert item.cnpj_discount_band == 15
    assert item.line_total == Decimal("85.00")

    assert repository.created is not None
    assert repository.created["subtotal"] == Decimal("85.00")


async def test_dois_produtos_somam_15_para_cada_um() -> None:
    # 10 + 20 = 30 no carrinho, mas sao produtos diferentes: cada linha 15%.
    repository = FakeRepository()
    order = await _create(
        repository,
        [
            OrderItemInput(product_id=_PRODUCT_A, quantity=10),
            OrderItemInput(product_id=_PRODUCT_B, quantity=20),
        ],
    )
    assert [(item.quantity, item.cnpj_discount_band) for item in order.items] == [
        (10, 15),
        (20, 15),
    ]
    assert order.subtotal == Decimal("2550.00")


async def test_mesmo_produto_30_e_10_aplica_30_e_15() -> None:
    repository = FakeRepository()
    order = await _create(
        repository,
        [
            OrderItemInput(product_id=_PRODUCT_A, quantity=30),
            OrderItemInput(product_id=_PRODUCT_B, quantity=10),
        ],
    )
    items = {item.sku: item for item in order.items}
    item_a = items[f"CNPJ-{_PRODUCT_A.hex[-4:]}"]
    item_b = items[f"CNPJ-{_PRODUCT_B.hex[-4:]}"]
    assert item_a.cnpj_discount_band == 30
    assert item_a.unit_price == Decimal("70.00")
    assert item_b.cnpj_discount_band == 15
    assert item_b.unit_price == Decimal("85.00")
    assert order.subtotal == Decimal("2950.00")


async def test_linhas_repetidas_somam_por_produto() -> None:
    repository = FakeRepository()
    order = await _create(
        repository,
        [
            OrderItemInput(product_id=_PRODUCT_A, quantity=20),
            OrderItemInput(product_id=_PRODUCT_A, quantity=20),
        ],
    )
    assert len(order.items) == 1
    item = order.items[0]
    assert item.quantity == 40
    assert item.cnpj_discount_band == 30
    assert item.unit_price == Decimal("70.00")
    assert order.subtotal == Decimal("2800.00")


async def test_person_nao_recebe_desconto_e_snapshot_fica_sem_cnpj() -> None:
    repository = FakeRepository(account_type="PERSON")
    order = await _create(repository, [OrderItemInput(product_id=_PRODUCT_A, quantity=1)])
    assert order.subtotal == Decimal("100.00")
    item = order.items[0]
    assert item.unit_price == Decimal("100.00")
    assert item.list_unit_price == Decimal("100.00")
    assert item.cnpj_discount_percent is None
    assert item.cnpj_discount_band is None


async def test_cupom_incide_sobre_valor_ja_descontado_pelo_cnpj() -> None:
    coupon = Coupon(code="CUPOM10", type=CouponType.PRODUCT_TOTAL, percent=Decimal("10.00"))
    repository = FakeRepository(coupon=coupon)
    order = await _create(
        repository,
        [OrderItemInput(product_id=_PRODUCT_A, quantity=1)],
        coupon_code="CUPOM10",
    )
    assert order.subtotal == Decimal("85.00")
    assert repository.created is not None
    assert repository.created["discount_total"] == Decimal("0.00")
    assert order.total == Decimal("76.50")


async def test_recovery_3pct_incide_sobre_valor_ja_descontado_pelo_cnpj() -> None:
    repository = FakeRepository(
        offer=RecoveryOfferView(id=_OFFER, type="PERCENT_DISCOUNT", percent=Decimal("3.00"))
    )
    order = await _create(repository, [OrderItemInput(product_id=_PRODUCT_A, quantity=1)])
    assert order.subtotal == Decimal("85.00")
    assert repository.created is not None
    assert repository.created["discount_total"] == Decimal("2.55")
    assert order.total == Decimal("82.45")


async def test_cupom_100_por_cento_nao_deixa_total_negativo() -> None:
    coupon = Coupon(code="GRATIS", type=CouponType.PRODUCT_TOTAL, percent=Decimal("100.00"))
    repository = FakeRepository(coupon=coupon)
    order = await _create(
        repository,
        [OrderItemInput(product_id=_PRODUCT_A, quantity=1)],
        coupon_code="GRATIS",
    )
    assert order.total == Decimal("0.00")


def test_payload_do_carrinho_nao_aceita_preco_ou_percentual() -> None:
    with pytest.raises(ValidationError):
        AddItemRequest.model_validate(
            {"product_id": str(_PRODUCT_A), "quantity": 1, "unit_price": "1.00"}
        )
    with pytest.raises(ValidationError):
        AddItemRequest.model_validate(
            {"product_id": str(_PRODUCT_A), "quantity": 30, "discount_percent": "30"}
        )
    with pytest.raises(ValidationError):
        AddItemRequest.model_validate(
            {"product_id": str(_PRODUCT_A), "quantity": 1, "account_type": "PERSON"}
        )


class _PaymentRepository:
    def __init__(self, *, total: Decimal) -> None:
        self.order = OrderForPayment(
            id=uuid.uuid4(),
            company_id=_COMPANY,
            status="RECEIVED",
            total=total,
            currency="BRL",
        )

    async def get_order_for_payment(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> OrderForPayment | None:
        return self.order

    async def create_payment(self, **kwargs: Any) -> PaymentView:
        return PaymentView(
            id=uuid.uuid4(),
            company_id=kwargs["company_id"],
            order_id=kwargs["order_id"],
            invoice_id=kwargs["invoice_id"],
            method=kwargs["method"].value,
            amount=kwargs["amount"],
            discount_amount=kwargs["discount_amount"],
            status="PENDING",
            provider=kwargs["provider"],
            provider_reference=kwargs["provider_reference"],
            created_at=datetime.now(UTC),
            paid_at=None,
        )


class _PaymentGateway:
    def __init__(self) -> None:
        self.amount: Decimal | None = None
        self.currency: str | None = None

    async def initiate(
        self,
        *,
        method: PaymentMethodPayment,
        amount: Decimal,
        currency: str,
        order_id: uuid.UUID,
        company_id: uuid.UUID,
        locale: str = "pt-BR",
    ) -> GatewayInstruction:
        self.amount = amount
        self.currency = currency
        return GatewayInstruction(provider="STRIPE", provider_reference="cs_test")


async def test_stripe_cobranca_usa_total_final_do_pedido_em_brl() -> None:
    # Pedido CNPJ de 10 luvas (15%) + 20 óculos (15%) = 2550 no carrinho.
    repository = _PaymentRepository(total=Decimal("2550.00"))
    gateway = _PaymentGateway()
    payment = await InitiatePayment(
        repository=cast(PaymentRepository, repository),
        gateway=gateway,
        pix_discount_rate=Decimal("0.05"),
    ).initiate(
        company_id=_COMPANY,
        order_id=repository.order.id,
        method=PaymentMethodPayment.CARD,
        idempotency_key="cnpj-stripe-0001",
    )

    assert gateway.amount == Decimal("2550.00")
    assert gateway.currency == "BRL"
    assert payment.amount == Decimal("2550.00")
    assert payment.discount_amount == Decimal("0.00")


def test_payload_do_pedido_nao_aceita_preco_ou_percentual() -> None:
    base = {"payment_method": "PIX"}
    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate(
            {
                **base,
                "items": [{"product_id": str(_PRODUCT_A), "quantity": 1, "unit_price": "1.00"}],
            }
        )
    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate(
            {
                **base,
                "items": [
                    {
                        "product_id": str(_PRODUCT_A),
                        "quantity": 30,
                        "cnpj_discount_percent": "30",
                    }
                ],
            }
        )
    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate(
            {
                **base,
                "items": [{"product_id": str(_PRODUCT_A), "quantity": 1}],
                "total": "1.00",
            }
        )
