"""Casos de uso de busca lexical (Fase 4): pesquisa + autocomplete.

O motor primario e o Elasticsearch; o PostgreSQL e o fallback. Os dados
comerciais (preco) sao hidratados do PostgreSQL e nunca vem do indice.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
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
    SearchSuggestion,
)

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
    """Pagina de busca lexical com modo real usado (lexical/fallback)."""

    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    pages: int
    search_mode: str


class SearchProducts:
    """Busca lexical paginada com fallback para PostgreSQL e hidratacao autoritativa."""

    def __init__(
        self,
        *,
        primary: SearchReader,
        fallback: SearchReader,
        product_reader: ProductReader,
        settings: Settings,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._product_reader = product_reader
        self._settings = settings

    async def run(self, *, query: SearchQuery, auth: AuthContext | None) -> SearchResultPage:
        self._validate(query)
        try:
            result = await self._primary.search(query)
        except SearchUnavailableError:
            _logger.warning("search_primary_unavailable_switching_to_fallback")
            result = await self._fallback.search(query)

        products = await self._product_reader.get_products_by_ids(
            [uuid.UUID(pid) for pid in result.ids]
        )
        today = date.today()
        items: list[SearchResultItem] = []
        dropped = 0
        for pid_str in result.ids:
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

        pages = (result.total + query.page_size - 1) // query.page_size
        return SearchResultPage(
            items=items,
            total=result.total,
            page=query.page,
            page_size=query.page_size,
            pages=pages,
            search_mode=result.mode,
        )

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


class AutocompleteProducts:
    """Autocomplete por nome/SKU; usa subcampo ``name.autocomplete`` do ES ou fallback Postgres."""

    def __init__(
        self,
        *,
        primary: SearchReader,
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
        try:
            return await self._primary.autocomplete(q=q, limit=limit)
        except SearchUnavailableError:
            _logger.warning("autocomplete_primary_unavailable_switching_to_fallback")
            return await self._fallback.autocomplete(q=q, limit=limit)
