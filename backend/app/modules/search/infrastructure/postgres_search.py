"""Adaptador de busca lexical de fallback no PostgreSQL.

Usa ``tsvector`` (configuracao ``portuguese``), ``unaccent`` e ``pg_trgm``
(ver migration ``0012_search_fallback_extensions``). Mantem o mesmo contrato
``SearchReader`` do Elasticsearch, permitindo que a camada de aplicacao
alterne entre os motores sem mudar a logica de negocio.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.ports import SearchQuery, SearchResult, SearchSuggestion

# Filtros base + match textual (SKU exato/prefixo, tsvector, trigram).
_SELECT_IDS = text(
    "SELECT p.id FROM products AS p "
    "WHERE p.status = 'ACTIVE' "
    "  AND (p.is_epi = false OR (p.ca_valid_until IS NOT NULL "
    "       AND p.ca_valid_until >= CURRENT_DATE)) "
    "  AND (:category_id IS NULL OR p.category_id = CAST(:category_id AS uuid)) "
    "  AND (:brand_id IS NULL OR p.brand_id = CAST(:brand_id AS uuid)) "
    "  AND (:is_epi IS NULL OR p.is_epi = :is_epi) "
    "  AND ( "
    "    :has_q = false "
    "    OR unaccent(LOWER(p.sku)) = unaccent(LOWER(:q)) "
    "    OR unaccent(LOWER(p.sku)) LIKE unaccent(LOWER(:q)) || '%' "
    "    OR to_tsvector('portuguese', p.name || ' ' || COALESCE(p.description, '')) "
    "        @@ plainto_tsquery('portuguese', unaccent(:q)) "
    "    OR p.name % :q "
    "  ) "
    "ORDER BY "
    "  CASE WHEN unaccent(LOWER(p.sku)) = unaccent(LOWER(:q)) THEN 0 ELSE 1 END, "
    "  CASE WHEN unaccent(LOWER(p.sku)) LIKE unaccent(LOWER(:q)) || '%' THEN 0 ELSE 1 END, "
    "  ts_rank_cd( "
    "    to_tsvector('portuguese', p.name || ' ' || COALESCE(p.description, '')), "
    "    plainto_tsquery('portuguese', unaccent(:q)) "
    "  ) DESC, "
    "  p.name ASC, p.id ASC "
    "LIMIT :page_size OFFSET :offset"
)

_COUNT = text(
    "SELECT COUNT(*) FROM products AS p "
    "WHERE p.status = 'ACTIVE' "
    "  AND (p.is_epi = false OR (p.ca_valid_until IS NOT NULL "
    "       AND p.ca_valid_until >= CURRENT_DATE)) "
    "  AND (:category_id IS NULL OR p.category_id = CAST(:category_id AS uuid)) "
    "  AND (:brand_id IS NULL OR p.brand_id = CAST(:brand_id AS uuid)) "
    "  AND (:is_epi IS NULL OR p.is_epi = :is_epi) "
    "  AND ( "
    "    :has_q = false "
    "    OR unaccent(LOWER(p.sku)) = unaccent(LOWER(:q)) "
    "    OR unaccent(LOWER(p.sku)) LIKE unaccent(LOWER(:q)) || '%' "
    "    OR to_tsvector('portuguese', p.name || ' ' || COALESCE(p.description, '')) "
    "        @@ plainto_tsquery('portuguese', unaccent(:q)) "
    "    OR p.name % :q "
    "  )"
)

_AUTOCOMPLETE = text(
    "SELECT p.id, p.sku, p.name FROM products AS p "
    "WHERE p.status = 'ACTIVE' "
    "  AND (p.is_epi = false OR (p.ca_valid_until IS NOT NULL "
    "       AND p.ca_valid_until >= CURRENT_DATE)) "
    "  AND ( "
    "      unaccent(LOWER(p.name)) LIKE '%' || unaccent(LOWER(:q)) || '%' "
    "      OR p.name % :q "
    "  ) "
    "ORDER BY p.name <-> :q "
    "LIMIT :limit"
)


class PostgresSearchReader:
    """Fallback de busca lexical sobre PostgreSQL (tsvector + unaccent + pg_trgm)."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def search(self, query: SearchQuery) -> SearchResult:
        q = query.q.strip() if query.q else ""
        has_q = bool(q)
        params: dict[str, Any] = {
            "q": q,
            "has_q": has_q,
            "category_id": str(query.category_id) if query.category_id is not None else None,
            "brand_id": str(query.brand_id) if query.brand_id is not None else None,
            "is_epi": query.is_epi,
            "page_size": query.page_size,
            "offset": (query.page - 1) * query.page_size,
        }
        count_params = {k: v for k, v in params.items() if k not in ("page_size", "offset")}
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_SELECT_IDS, params)).all()
            total = (await uow.session.execute(_COUNT, count_params)).scalar_one()
            await uow.commit()
        return SearchResult(
            ids=[str(row[0]) for row in rows],
            total=int(total),
            mode="postgres_fallback",
        )

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        q = q.strip()
        if not q:
            return []
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_AUTOCOMPLETE, {"q": q, "limit": limit})).all()
            await uow.commit()
        return [SearchSuggestion(id=str(row[0]), sku=str(row[1]), name=str(row[2])) for row in rows]
