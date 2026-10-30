"""Regra unica da oferta de recuperacao usada por preview e pedido."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.ordering.domain.checkout import calculate_recovery


def test_frete_gratis_nao_desconta_produtos() -> None:
    result = calculate_recovery(
        offer_type="FREE_SHIPPING",
        percent=None,
        eligible_product_total=Decimal("1000.00"),
    )
    assert result.discount == Decimal("0.00")
    assert result.free_shipping is True


def test_percentual_sobre_linhas_elegiveis() -> None:
    result = calculate_recovery(
        offer_type="PERCENT_DISCOUNT",
        percent=Decimal("3.00"),
        eligible_product_total=Decimal("1600.00"),
    )
    assert result.discount == Decimal("48.00")
    assert result.free_shipping is False


def test_percentual_arredonda_meio_para_cima() -> None:
    result = calculate_recovery(
        offer_type="PERCENT_DISCOUNT",
        percent=Decimal("3.00"),
        eligible_product_total=Decimal("10.01"),
    )
    assert result.discount == Decimal("0.30")


@pytest.mark.parametrize(
    ("offer_type", "percent", "total"),
    [
        ("UNKNOWN", None, "100.00"),
        ("PERCENT_DISCOUNT", None, "100.00"),
        ("PERCENT_DISCOUNT", Decimal("0"), "100.00"),
        ("PERCENT_DISCOUNT", Decimal("3.00"), "0.00"),
    ],
)
def test_sem_beneficio(offer_type: str, percent: Decimal | None, total: str) -> None:
    result = calculate_recovery(
        offer_type=offer_type,
        percent=percent,
        eligible_product_total=Decimal(total),
    )
    assert result.discount == Decimal("0.00")
    assert result.free_shipping is False
