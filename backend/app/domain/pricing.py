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

Desconto automatico CNPJ: ``resolve_cnpj_price`` aplica 15% a qualquer quantidade
e 30% a partir de 30 unidades do MESMO produto. ``resolve_customer_price``
compõe a regra da empresa/tier com esse desconto e e a unica entrada usada por
carrinho e pedidos, garantindo que o preco cobrado seja sempre o do servidor.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import IntEnum, StrEnum

# Desconto automatico para contas CNPJ (Company). Os percentuais e o limite
# ficam centralizados aqui: nenhum outro modulo repete estes numeros.
CNPJ_ACCOUNT_TYPE = "COMPANY"
CNPJ_STANDARD_DISCOUNT_PERCENT = Decimal("15.00")
CNPJ_VOLUME_DISCOUNT_PERCENT = Decimal("30.00")
CNPJ_VOLUME_MIN_QUANTITY = 30


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


class CnpjDiscountBand(IntEnum):
    """Faixa do desconto automatico CNPJ (0 = sem desconto)."""

    NONE = 0
    STANDARD = 15
    VOLUME = 30


@dataclass(frozen=True, kw_only=True)
class CnpjPrice:
    """Preco unitario apos o desconto automatico CNPJ.

    ``list_unit_price`` e o preco de tabela que serviu de base (o preco da
    empresa/tier antes do desconto CNPJ); ``unit_price`` e o valor final.
    """

    list_unit_price: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    discount_band: CnpjDiscountBand
    units_to_volume_discount: int | None


@dataclass(frozen=True, kw_only=True)
class ResolvedCustomerPrice:
    """Preco completo do cliente: regra da empresa + desconto CNPJ."""

    unit_price: Decimal
    list_unit_price: Decimal
    source: PriceSource
    rule_id: uuid.UUID | None
    tier_id: uuid.UUID | None
    tier_min_quantity: int | None
    discount_percent: Decimal
    discount_band: CnpjDiscountBand
    units_to_volume_discount: int | None


_CENTS = Decimal("0.01")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _require_decimal(name: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal, never float")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _validate_quantity(quantity: int) -> None:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError("quantity must be an int")
    if quantity < 1:
        raise ValueError("quantity must be at least 1")


def resolve_cnpj_price(*, account_type: str, quantity: int, list_unit_price: Decimal) -> CnpjPrice:
    """Aplica o desconto automatico CNPJ a uma linha de produto.

    Contas ``COMPANY`` (CNPJ) recebem 15% em qualquer quantidade e 30% a partir
    de ``CNPJ_VOLUME_MIN_QUANTITY`` unidades do MESMO produto. A decisao usa a
    quantidade da linha (nunca a soma do carrinho). Contas que nao sao CNPJ
    mantem o preco de tabela, sem desconto novo.

    Dinheiro sempre em ``Decimal`` com arredondamento ``ROUND_HALF_UP`` ao
    centavo. Quantidade invalida (nao inteira ou < 1) falha explicitamente.
    """
    _validate_quantity(quantity)
    list_price = _round_money(_require_decimal("list_unit_price", list_unit_price))
    if list_price < _ZERO:
        raise ValueError("list_unit_price must be non-negative")

    if account_type != CNPJ_ACCOUNT_TYPE:
        return CnpjPrice(
            list_unit_price=list_price,
            unit_price=list_price,
            discount_percent=_ZERO,
            discount_band=CnpjDiscountBand.NONE,
            units_to_volume_discount=None,
        )

    if quantity >= CNPJ_VOLUME_MIN_QUANTITY:
        percent = CNPJ_VOLUME_DISCOUNT_PERCENT
        band = CnpjDiscountBand.VOLUME
        units_to_volume_discount = None
    else:
        percent = CNPJ_STANDARD_DISCOUNT_PERCENT
        band = CnpjDiscountBand.STANDARD
        units_to_volume_discount = CNPJ_VOLUME_MIN_QUANTITY - quantity

    final_price = _round_money(list_price * (_HUNDRED - percent) / _HUNDRED)
    return CnpjPrice(
        list_unit_price=list_price,
        unit_price=final_price,
        discount_percent=percent,
        discount_band=band,
        units_to_volume_discount=units_to_volume_discount,
    )


def resolve_customer_price(
    *,
    account_type: str,
    base_unit_price: Decimal,
    tiers: list[PriceTier],
    quantity: int,
    category_id: uuid.UUID | None,
    rules: list[CompanyPriceRule],
) -> ResolvedCustomerPrice:
    """Resolve o preco final do cliente: regra da empresa e depois CNPJ.

    Esta e a UNICA entrada usada por carrinho e pedidos. O preco de tabela
    (``list_unit_price``) e o preco ja resolvido pela empresa/tier; o desconto
    CNPJ incide sobre ele. Cupom e recuperacao incidem depois, sobre o valor
    final da linha (fora desta funcao pura).
    """
    company = resolve_company_price(
        base_unit_price=base_unit_price,
        tiers=tiers,
        quantity=quantity,
        category_id=category_id,
        rules=rules,
    )
    cnpj = resolve_cnpj_price(
        account_type=account_type,
        quantity=quantity,
        list_unit_price=company.unit_price,
    )
    return ResolvedCustomerPrice(
        unit_price=cnpj.unit_price,
        list_unit_price=cnpj.list_unit_price,
        source=company.source,
        rule_id=company.rule_id,
        tier_id=company.tier_id,
        tier_min_quantity=company.tier_min_quantity,
        discount_percent=cnpj.discount_percent,
        discount_band=cnpj.discount_band,
        units_to_volume_discount=cnpj.units_to_volume_discount,
    )


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
