"""Testes unitarios da resolucao de preco por tier (dominio compartilhado)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.pricing import PriceTier, resolve_unit_price

_BASE = Decimal("24.90")


def _tier(min_qty: int, max_qty: int | None, price: str) -> PriceTier:
    return PriceTier(
        tier_id=uuid.uuid4(),
        min_quantity=min_qty,
        max_quantity=max_qty,
        unit_price=Decimal(price),
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
