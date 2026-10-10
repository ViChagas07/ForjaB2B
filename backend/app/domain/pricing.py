"""Resolucao de preco (regra de dominio compartilhada, pure Python).

Ordem de resolucao:
1. preco negociado da empresa (regra ``FIXED_PRICE`` de ``company_price_rules``);
2. desconto percentual da empresa sobre a lista (regra ``PERCENT_DISCOUNT``);
3. preco de lista: tier aplicavel a quantidade (``product_price_tiers``) ou
   ``base_unit_price``.

Para visitante (sem empresa) o preco nunca e resolvido aqui: a camada de
aplicacao expoe apenas ``price_on_request`` (preco consultivo). Usada pelos
contexts cart, ordering e search (que nao podem importar o modulo pricing,
bounded contexts independentes). Dinheiro sempre em ``Decimal``, arredondamento
``ROUND_HALF_UP`` ao centavo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


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


class PriceSource(StrEnum):
    """Origem do preco resolvido (para observabilidade e testes)."""

    NEGOTIATED = "NEGOTIATED"
    DISCOUNT = "DISCOUNT"
    LIST = "LIST"


@dataclass(frozen=True, kw_only=True)
class CompanyPriceRule:
    """Regra de preco de uma empresa (preco negociado ou desconto percentual).

    NUNCA contem dado de outra empresa: a leitura e sempre restrita ao tenant
    corrente (RLS). ``product_id`` identifica um preco negociado; ``category_id``
    (ou ``None`` = todas as categorias) identifica o escopo do desconto.
    """

    rule_id: uuid.UUID
    rule_type: str
    product_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    percent: Decimal | None = None
    unit_price: Decimal | None = None


@dataclass(frozen=True, kw_only=True)
class ResolvedCompanyPrice:
    """Preco resolvido para uma empresa, com a origem da regra aplicada."""

    unit_price: Decimal
    source: PriceSource
    rule_id: uuid.UUID | None
    tier_id: uuid.UUID | None
    tier_min_quantity: int | None


_CENTS = Decimal("0.01")
_HUNDRED = Decimal("100")


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def resolve_company_price(
    *,
    base_unit_price: Decimal,
    tiers: list[PriceTier],
    quantity: int,
    category_id: uuid.UUID | None,
    rules: list[CompanyPriceRule],
) -> ResolvedCompanyPrice:
    """Resolve o preco aplicando a precedencia empresa > lista.

    Precedencia (documentada em docs/CATALOG_DEMO.md):
    1. ``FIXED_PRICE`` negociado do produto (vence sempre);
    2. ``PERCENT_DISCOUNT`` da categoria do produto ou global, aplicado sobre o
       preco de lista (tier/base) e arredondado ao centavo (``ROUND_HALF_UP``);
    3. preco de lista (tier aplicavel ou ``base_unit_price``).

    ``rules`` deve conter apenas as regras aplicaveis ao produto; a categoria
    ainda e reconferida aqui como defesa.
    """
    listed = resolve_unit_price(base_unit_price=base_unit_price, tiers=tiers, quantity=quantity)

    negotiated: list[tuple[Decimal, CompanyPriceRule]] = []
    for rule in rules:
        if rule.rule_type == "FIXED_PRICE" and rule.unit_price is not None:
            negotiated.append((rule.unit_price, rule))
    if negotiated:
        best_price, best_rule = min(negotiated, key=lambda item: (item[0], str(item[1].rule_id)))
        return ResolvedCompanyPrice(
            unit_price=_round_money(best_price),
            source=PriceSource.NEGOTIATED,
            rule_id=best_rule.rule_id,
            tier_id=None,
            tier_min_quantity=None,
        )

    discounts: list[tuple[Decimal, CompanyPriceRule]] = []
    for rule in rules:
        if (
            rule.rule_type == "PERCENT_DISCOUNT"
            and rule.percent is not None
            and (rule.category_id is None or rule.category_id == category_id)
        ):
            discounts.append((rule.percent, rule))
    if discounts:
        best_percent, discount_rule = max(
            discounts,
            key=lambda item: (
                item[1].category_id is not None,
                item[0],
                str(item[1].rule_id),
            ),
        )
        discounted = listed.unit_price * (_HUNDRED - best_percent) / _HUNDRED
        return ResolvedCompanyPrice(
            unit_price=_round_money(discounted),
            source=PriceSource.DISCOUNT,
            rule_id=discount_rule.rule_id,
            tier_id=listed.tier_id,
            tier_min_quantity=listed.tier_min_quantity,
        )

    return ResolvedCompanyPrice(
        unit_price=_round_money(listed.unit_price),
        source=PriceSource.LIST,
        rule_id=None,
        tier_id=listed.tier_id,
        tier_min_quantity=listed.tier_min_quantity,
    )
