"""Casos de uso de busca (Fases 4 e 5): lexical + semantica + fallback.

O motor lexical e o Elasticsearch, o semantico e o pgvector e o fallback e o
PostgreSQL textual. Os dois primeiros rodam em paralelo e sao fundidos por
Reciprocal Rank Fusion (RRF); os dados comerciais (preco) sao hidratados do
PostgreSQL e nunca vem de indice ou vetor. O modo real usado e sempre exposto.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from app.application.security import AuthContext
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.product_availability import ca_status, is_sellable
from app.modules.search.application.errors import InvalidSearchQueryError, SearchUnavailableError
from app.modules.search.application.ports import (
    ProductReader,
    ProductRow,
    SearchQuery,
    SearchReader,
    SearchResult,
    SearchSuggestion,
)
from app.modules.search.application.rrf import looks_like_sku, reciprocal_rank_fusion
from app.modules.search.application.semantic import SemanticSearch

_logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class SearchResultItem:
    """Item hidratado da resposta de busca (sem preco quando visitante)."""

    id: uuid.UUID
    sku: str
    name: str
    slug: str
    status: str
    is_epi: bool
    ca_status: str
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    brand_id: uuid.UUID | None
    brand_name: str | None
    brand_slug: str | None
    base_unit_price: Decimal | None
    currency: str
    min_order_qty: int
    price_on_request: bool


@dataclass(frozen=True, kw_only=True)
class SearchResultPage:
    """Pagina de busca com o modo real (hybrid/lexical/semantic_postgres/fallback)."""

    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    pages: int
    search_mode: str


class SearchProducts:
    """Busca hibrida com degradacao graciosa e hidratacao autoritativa."""

    def __init__(
        self,
        *,
        primary: SearchReader | None,
        fallback: SearchReader,
        semantic: SemanticSearch | None,
        product_reader: ProductReader,
        settings: Settings,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._semantic = semantic
        self._product_reader = product_reader
        self._settings = settings

    async def run(self, *, query: SearchQuery, auth: AuthContext | None) -> SearchResultPage:
        self._validate(query)
        ids, total, mode = await self._retrieve(query)
        page_ids = self._paginate(ids, query=query, mode=mode)
        products = await self._product_reader.get_products_by_ids(
            [uuid.UUID(pid) for pid in page_ids]
        )
        today = date.today()
        items: list[SearchResultItem] = []
        dropped = 0
        for pid_str in page_ids:
            product = products.get(uuid.UUID(pid_str))
            if product is None:
                dropped += 1
                continue
            if not is_sellable(
                status=product.status,
                is_epi=product.is_epi,
                ca_valid_until=product.ca_valid_until,
                today=today,
            ):
                dropped += 1
                _logger.warning(
                    "search_stale_index_entry_dropped",
                    product_id=pid_str,
                    status=product.status,
                    ca_valid_until=str(product.ca_valid_until),
                )
                continue
            items.append(self._to_item(product, auth, today))
        if dropped:
            _logger.info("search_stale_entries_summary", dropped=dropped, returned=len(items))

        pages = (total + query.page_size - 1) // query.page_size
        return SearchResultPage(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            pages=pages,
            search_mode=mode,
        )

    async def _retrieve(self, query: SearchQuery) -> tuple[list[str], int, str]:
        """Executa os caminhos disponiveis, funde por RRF e informa o modo real."""
        use_semantic = self._use_semantic(query)
        retrieval_query = (
            replace(query, page=1, page_size=self._settings.embedding_candidate_limit)
            if use_semantic
            else query
        )
        lexical_outcome, semantic_outcome = await asyncio.gather(
            self._run_lexical(retrieval_query),
            self._run_semantic(query, enabled=use_semantic),
            return_exceptions=True,
        )
        lexical_ids, lexical_total = _as_lexical(lexical_outcome)
        semantic_ids = _as_semantic(semantic_outcome)

        if lexical_ids is not None and semantic_ids is not None:
            fused = reciprocal_rank_fusion(
                [lexical_ids, semantic_ids], k=self._settings.embedding_rrf_k
            )
            return fused, len(fused), "hybrid"
        if lexical_ids is not None:
            return lexical_ids, lexical_total, "lexical"
        if semantic_ids is not None:
            return semantic_ids, len(semantic_ids), "semantic_postgres"
        fallback = await self._fallback.search(query)
        return fallback.ids, fallback.total, fallback.mode

    def _use_semantic(self, query: SearchQuery) -> bool:
        text = (query.q or "").strip()
        return self._semantic is not None and bool(text) and not looks_like_sku(text)

    async def _run_lexical(self, query: SearchQuery) -> SearchResult | None:
        if self._primary is None:
            return None
        return await self._primary.search(query)

    async def _run_semantic(self, query: SearchQuery, *, enabled: bool) -> list[str] | None:
        semantic = self._semantic
        if not enabled or semantic is None:
            return None
        return await semantic.search_ids(query=query)

    def _paginate(self, ids: list[str], *, query: SearchQuery, mode: str) -> list[str]:
        # Retrieval limitado por candidatos (RRF/semantico) e paginado aqui;
        # lexical e fallback textual ja vem paginados pelo proprio motor.
        bounded = mode != "postgres_fallback" and self._use_semantic(query)
        if not bounded:
            return ids
        start = (query.page - 1) * query.page_size
        return ids[start : start + query.page_size]

    def _validate(self, query: SearchQuery) -> None:
        if query.q is not None and len(query.q) > self._settings.search_max_query_length:
            raise InvalidSearchQueryError(
                f"query exceeds {self._settings.search_max_query_length} characters"
            )
        if query.page < 1:
            raise InvalidSearchQueryError("page must be >= 1")
        if query.page_size < 1 or query.page_size > self._settings.search_max_page_size:
            raise InvalidSearchQueryError(
                f"page_size must be between 1 and {self._settings.search_max_page_size}"
            )
        if (query.page - 1) * query.page_size > self._settings.search_max_deep_pagination:
            raise InvalidSearchQueryError("pagination too deep")

    def _to_item(
        self, product: ProductRow, auth: AuthContext | None, today: date
    ) -> SearchResultItem:
        price_on_request = auth is None
        return SearchResultItem(
            id=product.id,
            sku=product.sku,
            name=product.name,
            slug=product.slug,
            status=product.status,
            is_epi=product.is_epi,
            ca_status=ca_status(
                is_epi=product.is_epi,
                ca_valid_until=product.ca_valid_until,
                today=today,
            ).value,
            category_id=product.category_id,
            category_name=product.category_name,
            category_slug=product.category_slug,
            brand_id=product.brand_id,
            brand_name=product.brand_name,
            brand_slug=product.brand_slug,
            base_unit_price=None if price_on_request else product.base_unit_price,
            currency=product.currency,
            min_order_qty=product.min_order_qty,
            price_on_request=price_on_request,
        )


def _as_lexical(outcome: SearchResult | None | BaseException) -> tuple[list[str] | None, int]:
    if isinstance(outcome, SearchResult):
        return outcome.ids, outcome.total
    if isinstance(outcome, BaseException):
        _logger.warning("lexical_search_unavailable", error=type(outcome).__name__)
    return None, 0


def _as_semantic(outcome: list[str] | None | BaseException) -> list[str] | None:
    if isinstance(outcome, list):
        return outcome
    if isinstance(outcome, BaseException):
        _logger.warning("semantic_search_unavailable", error=type(outcome).__name__)
    return None


class AutocompleteProducts:
    """Autocomplete por nome/SKU; usa o subcampo ``name.autocomplete`` do ES ou fallback."""

    def __init__(
        self,
        *,
        primary: SearchReader | None,
        fallback: SearchReader,
        settings: Settings,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._settings = settings

    async def run(self, *, q: str) -> list[SearchSuggestion]:
        q = q.strip()
        if len(q) < self._settings.search_autocomplete_min_chars:
            return []
        limit = self._settings.search_autocomplete_max_suggestions
        if self._primary is not None:
            try:
                return await self._primary.autocomplete(q=q, limit=limit)
            except SearchUnavailableError:
                _logger.warning("autocomplete_primary_unavailable_switching_to_fallback")
        return await self._fallback.autocomplete(q=q, limit=limit)
