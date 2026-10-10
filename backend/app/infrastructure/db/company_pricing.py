"""Leitura compartilhada das regras de preco por empresa (tenant-scoped).

Os repositorios de cart e ordering e o leitor do modulo de busca chamam
``load_company_price_rules`` DENTRO de uma UoW ja aberta com contexto de tenant
(``app.set_tenant_context``): a RLS de ``company_price_rules`` garante que
somente as regras da empresa corrente retornem. Sem contexto de tenant o
resultado e vazio (nunca vaza preco entre empresas).

A consulta junta ``products`` (global) para descobrir, por produto, as regras
aplicaveis: o preco negociado do produto e/ou o desconto da categoria (ou
global). O calculo da precedencia (negociado > desconto > lista) fica no
dominio (``app.domain.pricing.resolve_company_price``).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pricing import CompanyPriceRule

_LOAD_RULES = text(
    "SELECT p.id AS matched_product_id, r.id, r.rule_type, r.product_id, r.category_id, "
    "r.percent, r.unit_price "
    "FROM products AS p "
    "JOIN company_price_rules AS r "
    "  ON r.product_id = p.id "
    "  OR (r.rule_type = 'PERCENT_DISCOUNT' "
    "      AND (r.category_id IS NULL OR r.category_id = p.category_id)) "
    "WHERE p.id = ANY(CAST(:product_ids AS uuid[]))"
)


async def load_company_price_rules(
    session: AsyncSession, *, product_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[CompanyPriceRule]]:
    """Regras aplicaveis por produto, restritas ao tenant corrente (RLS).

    Devolve um mapa ``product_id -> [CompanyPriceRule, ...]`` (lista vazia
    quando nao ha regra, ou quando nao ha contexto de tenant).
    """
    result: dict[uuid.UUID, list[CompanyPriceRule]] = {pid: [] for pid in product_ids}
    if not product_ids:
        return result
    rows = (
        await session.execute(_LOAD_RULES, {"product_ids": [str(pid) for pid in product_ids]})
    ).all()
    for row in rows:
        result[row.matched_product_id].append(
            CompanyPriceRule(
                rule_id=row.id,
                rule_type=row.rule_type,
                product_id=row.product_id,
                category_id=row.category_id,
                percent=row.percent,
                unit_price=row.unit_price,
            )
        )
    return result
