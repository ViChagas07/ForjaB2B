"""Resolucao de preco (regra de dominio compartilhada, pure Python).

Ordem de resolucao (Fase 1, secao 15):
1. tabela de preco negociado por cliente (quando existir, fora do schema F1);
2. tier aplicavel a quantidade (``product_price_tiers``);
3. ``base_unit_price``.

Usada pelos contexts cart e ordering (que nao podem importar o modulo pricing,
bounded contexts independentes). Dinheiro sempre em ``Decimal``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, kw_only=True)
class PriceTier:
    """Faixa de preco aplicavel a uma quantidade."""

    tier_id: uuid.UUID
    min_quantity: int
    max_quantity: int | None
    unit_price: Decimal


@dataclass(frozen=True, kw_only=True)
class ResolvedPrice:
    """Preco resolvido para uma quantidade de um produto."""

    unit_price: Decimal
    tier_id: uuid.UUID | None
    tier_min_quantity: int | None


def resolve_unit_price(
    *, base_unit_price: Decimal, tiers: list[PriceTier], quantity: int
) -> ResolvedPrice:
    """Resolve o preco unitario para ``quantity`` (tier mais especifico ou base).

    Entre tiers aplicaveis (``min <= qty <= max``), vence o de MAIOR
    ``min_quantity`` (mais especifico). Sem tier aplicavel, usa o preco base.
    """
    applicable = [
        t
        for t in tiers
        if t.min_quantity <= quantity and (t.max_quantity is None or quantity <= t.max_quantity)
    ]
    if applicable:
        best = max(applicable, key=lambda t: t.min_quantity)
        return ResolvedPrice(
            unit_price=best.unit_price,
            tier_id=best.tier_id,
            tier_min_quantity=best.min_quantity,
        )
    return ResolvedPrice(unit_price=base_unit_price, tier_id=None, tier_min_quantity=None)
