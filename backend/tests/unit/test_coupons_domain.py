"""Regras puras de codigo de cupom (normalizacao e formato)."""

from __future__ import annotations

import pytest

from app.modules.ordering.domain.coupon import (
    CouponRedemptionStatus,
    CouponType,
    is_valid_coupon_code,
    normalize_coupon_code,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  black-friday  ", "BLACK-FRIDAY"),
        ("cupom_10", "CUPOM_10"),
        ("AbC123", "ABC123"),
    ],
)
def test_normaliza_codigo_com_trim_e_maiusculas(raw: str, expected: str) -> None:
    assert normalize_coupon_code(raw) == expected


@pytest.mark.parametrize(
    "code",
    ["ABCD", "A1B2-C3D4", "CUPOM_10", "X" * 32],
)
def test_codigo_valido(code: str) -> None:
    assert is_valid_coupon_code(code) is True


@pytest.mark.parametrize(
    "code",
    ["ABC", "A" * 33, "abc", "CUPOM 10", "CUPOM.10", "ÁBC1", ""],
)
def test_codigo_invalido(code: str) -> None:
    assert is_valid_coupon_code(code) is False


def test_enums_estaveis() -> None:
    assert CouponType.PRODUCT_TOTAL.value == "PRODUCT_TOTAL"
    assert CouponType.SHIPPING.value == "SHIPPING"
    assert CouponRedemptionStatus.APPLIED.value == "APPLIED"
    assert CouponRedemptionStatus.RELEASED.value == "RELEASED"
