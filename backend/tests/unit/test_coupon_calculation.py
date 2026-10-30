"""Calculo puro de descontos: ordem recovery -> cupom -> frete -> PIX."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from app.modules.ordering.domain.coupon import (
    Coupon,
    CouponType,
    DiscountKind,
    OrderTotals,
    calculate_order_totals,
)

_ZERO = Decimal("0.00")


def _coupon(
    *,
    coupon_type: CouponType = CouponType.PRODUCT_TOTAL,
    percent: str = "10.00",
    max_discount: str | None = None,
) -> Coupon:
    return Coupon(
        code="CUPOM-TESTE",
        type=coupon_type,
        percent=Decimal(percent),
        max_discount_amount=Decimal(max_discount) if max_discount is not None else None,
    )


def _calculate(
    *,
    subtotal: str = "1000.00",
    shipping: str = "0.00",
    coupon: Coupon | None = None,
    recovery: str = "0.00",
    pix_rate: str | None = None,
) -> OrderTotals:
    return calculate_order_totals(
        subtotal=Decimal(subtotal),
        shipping=Decimal(shipping),
        coupon=coupon,
        recovery_discount=Decimal(recovery),
        pix_discount_rate=Decimal(pix_rate) if pix_rate is not None else None,
    )


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        ("5.00", "50.00"),
        ("10.00", "100.00"),
        ("15.00", "150.00"),
        ("20.00", "200.00"),
        ("100.00", "1000.00"),
    ],
)
def test_percentuais_do_produto(percent: str, expected: str) -> None:
    result = _calculate(coupon=_coupon(percent=percent))
    assert result.coupon_discount == Decimal(expected)
    assert result.total == Decimal("1000.00") - Decimal(expected)
    assert DiscountKind.COUPON_PRODUCT in result.applied_discounts


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        ("5.00", "5.00"),
        ("10.00", "10.00"),
        ("100.00", "100.00"),
    ],
)
def test_percentuais_do_frete(percent: str, expected: str) -> None:
    result = _calculate(
        subtotal="0.00",
        shipping="100.00",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent=percent),
    )
    assert result.shipping_discount == Decimal(expected)
    assert result.total == Decimal("100.00") - Decimal(expected)
    assert DiscountKind.COUPON_SHIPPING in result.applied_discounts


def test_teto_do_desconto_no_produto() -> None:
    result = _calculate(
        coupon=_coupon(percent="50.00", max_discount="100.00"),
        subtotal="1000.00",
    )
    assert result.coupon_discount == Decimal("100.00")
    assert result.total == Decimal("900.00")


def test_teto_do_desconto_no_frete() -> None:
    result = _calculate(
        subtotal="0.00",
        shipping="100.00",
        coupon=_coupon(
            coupon_type=CouponType.SHIPPING,
            percent="50.00",
            max_discount="30.00",
        ),
    )
    assert result.shipping_discount == Decimal("30.00")
    assert result.total == Decimal("70.00")


def test_cupom_de_100_por_cento_nao_ultrapassa_o_subtotal() -> None:
    result = _calculate(
        subtotal="100.00",
        coupon=_coupon(percent="100.00", max_discount="500.00"),
    )
    assert result.coupon_discount == Decimal("100.00")
    assert result.total == _ZERO


def test_frete_zero_com_cupom_de_frete() -> None:
    result = _calculate(
        subtotal="0.00",
        shipping="0.00",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent="100.00"),
    )
    assert result.shipping_discount == _ZERO
    assert result.total == _ZERO
    assert result.applied_discounts == frozenset()


def test_recovery_aplicado_sem_cupom() -> None:
    result = _calculate(recovery="30.00")
    assert result.recovery_discount == Decimal("30.00")
    assert result.total == Decimal("970.00")
    assert result.applied_discounts == frozenset({DiscountKind.RECOVERY})


def test_cupom_de_produto_desliga_recovery() -> None:
    result = _calculate(recovery="30.00", coupon=_coupon(percent="10.00"))
    assert result.recovery_discount == _ZERO
    assert result.coupon_discount == Decimal("100.00")
    assert result.total == Decimal("900.00")
    assert result.applied_discounts == frozenset({DiscountKind.COUPON_PRODUCT})


def test_cupom_de_frete_permite_recovery() -> None:
    result = _calculate(
        recovery="30.00",
        shipping="100.00",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent="10.00"),
    )
    assert result.recovery_discount == Decimal("30.00")
    assert result.shipping_discount == Decimal("10.00")
    assert result.total == Decimal("1060.00")
    assert result.applied_discounts == frozenset(
        {DiscountKind.RECOVERY, DiscountKind.COUPON_SHIPPING}
    )


def test_recovery_limitado_ao_subtotal() -> None:
    result = _calculate(recovery="1500.00")
    assert result.recovery_discount == Decimal("1000.00")
    assert result.total == _ZERO


def test_pix_incide_sobre_o_total_apos_cupom_de_produto() -> None:
    result = _calculate(coupon=_coupon(percent="10.00"), pix_rate="0.05")
    assert result.coupon_discount == Decimal("100.00")
    assert result.pix_discount == Decimal("45.00")
    assert result.total == Decimal("855.00")
    assert result.applied_discounts == frozenset({DiscountKind.COUPON_PRODUCT, DiscountKind.PIX})


def test_pix_incide_sobre_frete_apos_cupom_de_frete() -> None:
    result = _calculate(
        shipping="100.00",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent="10.00"),
        pix_rate="0.05",
    )
    assert result.shipping_discount == Decimal("10.00")
    assert result.pix_discount == Decimal("54.50")
    assert result.total == Decimal("1035.50")


def test_pix_desligado_por_flag_ausente() -> None:
    result = _calculate(coupon=_coupon(percent="10.00"), pix_rate=None)
    assert result.pix_discount == _ZERO
    assert DiscountKind.PIX not in result.applied_discounts


def test_pix_com_taxa_zero_nao_desconta() -> None:
    result = _calculate(pix_rate="0.00")
    assert result.pix_discount == _ZERO
    assert DiscountKind.PIX not in result.applied_discounts


def test_pix_de_100_por_cento_zera_o_total_sem_negativar() -> None:
    result = _calculate(pix_rate="1.00")
    assert result.pix_discount == Decimal("1000.00")
    assert result.total == _ZERO


def test_arredondamento_do_cupom_de_produto() -> None:
    result = _calculate(subtotal="99.99", coupon=_coupon(percent="5.00"))
    assert result.coupon_discount == Decimal("5.00")
    assert result.total == Decimal("94.99")


def test_arredondamento_do_cupom_de_frete() -> None:
    result = _calculate(
        subtotal="0.00",
        shipping="10.05",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent="10.00"),
    )
    assert result.shipping_discount == Decimal("1.01")
    assert result.total == Decimal("9.04")


def test_total_nunca_negativo_com_descontos_no_limite() -> None:
    result = _calculate(
        subtotal="1000.00",
        shipping="100.00",
        recovery="5000.00",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent="100.00"),
    )
    assert result.recovery_discount == Decimal("1000.00")
    assert result.shipping_discount == Decimal("100.00")
    assert result.total == _ZERO


def test_composicao_completa_recovery_cupom_frete_e_pix() -> None:
    result = _calculate(
        subtotal="1000.00",
        shipping="200.00",
        recovery="50.00",
        coupon=_coupon(coupon_type=CouponType.SHIPPING, percent="10.00"),
        pix_rate="0.05",
    )
    assert result.recovery_discount == Decimal("50.00")
    assert result.shipping_discount == Decimal("20.00")
    assert result.pix_discount == Decimal("56.50")
    assert result.total == Decimal("1073.50")


def test_taxa_pix_acima_de_100_por_cento_e_rejeitada() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        _calculate(pix_rate="1.01")


@pytest.mark.parametrize("value", ["-0.01", "-100.00"])
def test_entradas_negativas_sao_rejeitadas(value: str) -> None:
    with pytest.raises(ValueError):
        _calculate(subtotal=value)


def test_float_e_rejeitado() -> None:
    with pytest.raises(TypeError, match="never float"):
        calculate_order_totals(
            subtotal=cast(Decimal, 1000.0),
            shipping=Decimal("0.00"),
        )


@pytest.mark.parametrize("percent", ["0.00", "100.01"])
def test_percentual_invalido_e_rejeitado(percent: str) -> None:
    with pytest.raises(ValueError, match="coupon percent"):
        _calculate(coupon=_coupon(percent=percent))
