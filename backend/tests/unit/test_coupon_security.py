"""Testes adversariais de entrada e mass assignment do sistema de cupons."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponType,
    calculate_order_totals,
    is_valid_coupon_code,
    normalize_coupon_code,
)
from app.modules.ordering.domain.coupon_admin import (
    CouponCreateData,
    CouponValidationError,
    prepare_coupon_create,
)
from app.modules.ordering.interface.coupon_admin_schemas import CouponCreate
from app.modules.ordering.interface.schemas import (
    CouponPreviewRequest,
    CreateOrderRequest,
)

_PRODUCT_ID = UUID("33333333-3333-4333-8333-333333333333")


def test_order_rejeita_desconto_total_e_outros_campos_extras() -> None:
    payload = {
        "items": [{"product_id": str(_PRODUCT_ID), "quantity": 1}],
        "payment_method": "PIX",
        "idempotency_key": "security-order-1",
        "coupon_code": "CUPOM10",
        "coupon_discount_amount": "999.00",
        "discount_total": "999.00",
        "total": "0.00",
        "percent": "100.00",
    }
    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate(payload)


def test_preview_rejeita_valores_calculados_pelo_cliente() -> None:
    with pytest.raises(ValidationError):
        CouponPreviewRequest.model_validate(
            {"code": "CUPOM10", "payment_method": "PIX", "total": "0.00"}
        )


def test_admin_rejeita_campos_extras_no_create() -> None:
    with pytest.raises(ValidationError):
        CouponCreate.model_validate(
            {
                "code": "CUPOM10",
                "type": "PRODUCT_TOTAL",
                "percent": "10.00",
                "discount_amount": "999.00",
            }
        )


@pytest.mark.parametrize(
    "code",
    [
        "<script>alert(1)</script>",
        "'; DROP TABLE coupons; --",
        "CUPOM 10",
        "\u0421UPOM10",  # C cirilico (homoglifo)
        "CUPOM\u0000",
        "A" * 33,
        "ABC",
    ],
)
def test_codigo_hostil_nao_passa_no_dominio(code: str) -> None:
    normalized = normalize_coupon_code(code)
    assert is_valid_coupon_code(normalized) is False
    with pytest.raises(CouponValidationError):
        prepare_coupon_create(
            CouponCreateData(
                code=code,
                type=CouponType.PRODUCT_TOTAL,
                percent=Decimal("10.00"),
            )
        )


def test_aritmetica_com_valores_enormes_nao_estoura() -> None:
    coupon = Coupon(
        code="CUPOM10",
        type=CouponType.PRODUCT_TOTAL,
        percent=Decimal("100.00"),
        max_discount_amount=Decimal("999999999999.99"),
    )
    totals = calculate_order_totals(
        subtotal=Decimal("999999999999.99"),
        shipping=Decimal("0.00"),
        coupon=coupon,
    )
    assert totals.total == Decimal("0.00")
    assert totals.coupon_discount == Decimal("999999999999.99")


def test_cupom_de_frete_100_por_cento_com_frete_zero() -> None:
    coupon = Coupon(
        code="FRETE",
        type=CouponType.SHIPPING,
        percent=Decimal("100.00"),
    )
    totals = calculate_order_totals(
        subtotal=Decimal("100.00"),
        shipping=Decimal("0.00"),
        coupon=coupon,
    )
    assert totals.shipping_discount == Decimal("0.00")
    assert totals.total == Decimal("100.00")
