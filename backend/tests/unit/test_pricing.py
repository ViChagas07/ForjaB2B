"""Testes unitarios da resolucao de preco (dominio compartilhado).

Cobre a resolucao por tier/base (``resolve_unit_price``) e a precedencia de
preco por empresa (``resolve_company_price``): negociado > desconto > lista.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.pricing import (
    CompanyPriceRule,
    PriceSource,
    PriceTier,
    resolve_company_price,
    resolve_unit_price,
)

_BASE = Decimal("24.90")
_CATEGORY = uuid.UUID("00000000-0000-0000-0000-000000000401")
_OTHER_CATEGORY = uuid.UUID("00000000-0000-0000-0000-000000000402")


def _tier(min_qty: int, max_qty: int | None, price: str) -> PriceTier:
    return PriceTier(
        tier_id=uuid.uuid4(),
        min_quantity=min_qty,
        max_quantity=max_qty,
        unit_price=Decimal(price),
    )


def _fixed(price: str, *, category: uuid.UUID | None = None) -> CompanyPriceRule:
    return CompanyPriceRule(
        rule_id=uuid.uuid4(),
        rule_type="FIXED_PRICE",
        product_id=uuid.uuid4(),
        category_id=category,
        unit_price=Decimal(price),
    )


def _discount(percent: str, *, category: uuid.UUID | None = None) -> CompanyPriceRule:
    return CompanyPriceRule(
        rule_id=uuid.uuid4(),
        rule_type="PERCENT_DISCOUNT",
        category_id=category,
        percent=Decimal(percent),
    )


def test_abaixo_do_primeiro_tier_usa_preco_base() -> None:
    tiers = [_tier(6, 23, "24.90"), _tier(24, None, "21.90")]
    resolved = resolve_unit_price(base_unit_price=_BASE, tiers=tiers, quantity=1)
    assert resolved.unit_price == _BASE
    assert resolved.tier_id is None


def test_exatamente_no_inicio_do_tier() -> None:
    tiers = [_tier(6, 23, "24.90"), _tier(24, None, "21.90")]
    resolved = resolve_unit_price(base_unit_price=_BASE, tiers=tiers, quantity=6)
    assert resolved.unit_price == Decimal("24.90")
    assert resolved.tier_min_quantity == 6


def test_exatamente_no_fim_do_tier() -> None:
    tiers = [_tier(6, 23, "24.90"), _tier(24, None, "21.90")]
    resolved = resolve_unit_price(base_unit_price=_BASE, tiers=tiers, quantity=23)
    assert resolved.unit_price == Decimal("24.90")


def test_entre_tiers() -> None:
    tiers = [_tier(6, 23, "24.90"), _tier(24, None, "21.90")]
    resolved = resolve_unit_price(base_unit_price=_BASE, tiers=tiers, quantity=24)
    assert resolved.unit_price == Decimal("21.90")
    assert resolved.tier_min_quantity == 24


def test_tier_sem_maximo() -> None:
    tiers = [_tier(6, 23, "24.90"), _tier(24, None, "21.90")]
    resolved = resolve_unit_price(base_unit_price=_BASE, tiers=tiers, quantity=1000)
    assert resolved.unit_price == Decimal("21.90")


def test_produto_sem_tier_usa_preco_base() -> None:
    resolved = resolve_unit_price(base_unit_price=Decimal("899.00"), tiers=[], quantity=10)
    assert resolved.unit_price == Decimal("899.00")


def test_precisao_monetaria() -> None:
    tiers = [_tier(1, None, "1.10")]
    resolved = resolve_unit_price(base_unit_price=Decimal("1.20"), tiers=tiers, quantity=3)
    assert resolved.unit_price == Decimal("1.10")
    assert resolved.unit_price * 3 == Decimal("3.30")


def _company_price(rules: list[CompanyPriceRule], *, quantity: int = 1) -> Decimal:
    return resolve_company_price(
        base_unit_price=_BASE,
        tiers=[],
        quantity=quantity,
        category_id=_CATEGORY,
        rules=rules,
    ).unit_price


def test_sem_regras_usa_preco_de_lista() -> None:
    resolved = resolve_company_price(
        base_unit_price=_BASE, tiers=[], quantity=1, category_id=_CATEGORY, rules=[]
    )
    assert resolved.unit_price == _BASE
    assert resolved.source is PriceSource.LIST
    assert resolved.rule_id is None


def test_preco_negociado_vence_desconto_e_lista() -> None:
    rules = [_discount("10", category=_CATEGORY), _fixed("19.90")]
    resolved = resolve_company_price(
        base_unit_price=_BASE, tiers=[], quantity=1, category_id=_CATEGORY, rules=rules
    )
    assert resolved.unit_price == Decimal("19.90")
    assert resolved.source is PriceSource.NEGOTIATED
    assert resolved.tier_min_quantity is None


def test_desconto_da_categoria_aplicado_sobre_a_lista() -> None:
    resolved = resolve_company_price(
        base_unit_price=Decimal("100.00"),
        tiers=[],
        quantity=1,
        category_id=_CATEGORY,
        rules=[_discount("15", category=_CATEGORY)],
    )
    assert resolved.unit_price == Decimal("85.00")
    assert resolved.source is PriceSource.DISCOUNT


def test_desconto_global_vale_para_qualquer_categoria() -> None:
    assert _company_price([_discount("10")]) == Decimal("22.41")
    assert _company_price([_discount("10")], quantity=5) == Decimal("22.41")


def test_desconto_de_categoria_vence_o_global() -> None:
    rules = [_discount("5"), _discount("20", category=_CATEGORY)]
    resolved = resolve_company_price(
        base_unit_price=Decimal("100.00"),
        tiers=[],
        quantity=1,
        category_id=_CATEGORY,
        rules=rules,
    )
    assert resolved.unit_price == Decimal("80.00")


def test_desconto_de_outra_categoria_nao_se_aplica() -> None:
    resolved = resolve_company_price(
        base_unit_price=Decimal("100.00"),
        tiers=[],
        quantity=1,
        category_id=_CATEGORY,
        rules=[_discount("20", category=_OTHER_CATEGORY)],
    )
    assert resolved.unit_price == Decimal("100.00")
    assert resolved.source is PriceSource.LIST


def test_desconto_incide_sobre_o_tier_da_quantidade() -> None:
    tiers = [_tier(10, None, "20.00")]
    resolved = resolve_company_price(
        base_unit_price=_BASE,
        tiers=tiers,
        quantity=10,
        category_id=_CATEGORY,
        rules=[_discount("25", category=_CATEGORY)],
    )
    assert resolved.unit_price == Decimal("15.00")
    assert resolved.tier_min_quantity == 10


def test_arredondamento_half_up_ao_centavo() -> None:
    # 24.90 * 0.95 = 23.655 -> 23.66 (ROUND_HALF_UP)
    assert _company_price([_discount("5")]) == Decimal("23.66")
