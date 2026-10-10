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
    "  AND (CAST(:category_id AS uuid) IS NULL "
    "       OR p.category_id = CAST(:category_id AS uuid)) "
    "  AND (CAST(:brand_id AS uuid) IS NULL OR p.brand_id = CAST(:brand_id AS uuid)) "
    "  AND (CAST(:is_epi AS boolean) IS NULL OR p.is_epi = CAST(:is_epi AS boolean)) "
    "  AND ( "
    "    CAST(:has_q AS boolean) = false "
    "    OR unaccent(LOWER(p.sku)) = unaccent(LOWER(CAST(:q AS text))) "
    "    OR unaccent(LOWER(p.sku)) LIKE unaccent(LOWER(CAST(:q AS text))) || '%' "
    "    OR to_tsvector('portuguese', p.name || ' ' || COALESCE(p.description, '')) "
    "        @@ plainto_tsquery('portuguese', unaccent(CAST(:q AS text))) "
    "    OR p.name % CAST(:q AS text) "
    "  ) "
    "ORDER BY "
    "  CASE WHEN unaccent(LOWER(p.sku)) = unaccent(LOWER(CAST(:q AS text))) "
    "       THEN 0 ELSE 1 END, "
    "  CASE WHEN unaccent(LOWER(p.sku)) LIKE unaccent(LOWER(CAST(:q AS text))) || '%' "
    "       THEN 0 ELSE 1 END, "
    "  ts_rank_cd( "
    "    to_tsvector('portuguese', p.name || ' ' || COALESCE(p.description, '')), "
    "    plainto_tsquery('portuguese', unaccent(CAST(:q AS text))) "
    "  ) DESC, "
    "  p.name ASC, p.id ASC "
    "LIMIT CAST(:page_size AS integer) OFFSET CAST(:offset AS integer)"
)

_COUNT = text(
    "SELECT COUNT(*) FROM products AS p "
    "WHERE p.status = 'ACTIVE' "
    "  AND (p.is_epi = false OR (p.ca_valid_until IS NOT NULL "
    "       AND p.ca_valid_until >= CURRENT_DATE)) "
    "  AND (CAST(:category_id AS uuid) IS NULL "
    "       OR p.category_id = CAST(:category_id AS uuid)) "
    "  AND (CAST(:brand_id AS uuid) IS NULL OR p.brand_id = CAST(:brand_id AS uuid)) "
    "  AND (CAST(:is_epi AS boolean) IS NULL OR p.is_epi = CAST(:is_epi AS boolean)) "
    "  AND ( "
    "    CAST(:has_q AS boolean) = false "
    "    OR unaccent(LOWER(p.sku)) = unaccent(LOWER(CAST(:q AS text))) "
    "    OR unaccent(LOWER(p.sku)) LIKE unaccent(LOWER(CAST(:q AS text))) || '%' "
    "    OR to_tsvector('portuguese', p.name || ' ' || COALESCE(p.description, '')) "
    "        @@ plainto_tsquery('portuguese', unaccent(CAST(:q AS text))) "
    "    OR p.name % CAST(:q AS text) "
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
