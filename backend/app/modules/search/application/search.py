"""Casos de uso de busca (Fases 4 e 5): lexical + semantica + fallback.

O motor lexical e o Elasticsearch, o semantico e o pgvector e o fallback e o
PostgreSQL textual. Os dois primeiros rodam em paralelo e sao fundidos por
Reciprocal Rank Fusion (RRF); os dados comerciais (preco) sao hidratados do
PostgreSQL e nunca vem de indice ou vetor. O modo real usado e sempre exposto.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from app.application.i18n import resolve_product_text
from app.application.security import AuthContext
from app.core import metrics
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.catalog_image import resolve_image_alt, resolve_product_image_path
from app.domain.i18n import DEFAULT_LOCALE
from app.domain.pricing import CompanyPriceRule, resolve_company_price
from app.domain.product_availability import ca_status, is_sellable
from app.modules.search.application.errors import InvalidSearchQueryError, SearchUnavailableError
from app.modules.search.application.ports import (
    ProductReader,
    ProductRow,
    SearchQuery,
    SearchReader,
    SearchResult,
    SearchSuggestion,
    SuggestCategory,
    SuggestData,
    SuggestTerm,
)
from app.modules.search.application.rrf import looks_like_sku, reciprocal_rank_fusion
from app.modules.search.application.semantic import SemanticSearch

_logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class SearchResultItem:
    """Item hidratado da resposta de busca (sem preco quando bloqueado)."""

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
    image_url: str
    image_alt: str
    content_locale: str


@dataclass(frozen=True, kw_only=True)
class SearchResultPage:
    """Pagina de busca com o modo real (hybrid/lexical/semantic_postgres/fallback)."""

    items: list[SearchResultItem]
    total: int
    page: int
    page_size: int
    pages: int
    search_mode: str


@dataclass(frozen=True, kw_only=True)
class SuggestResult:
    """Sugestoes do dropdown: termos, categorias e produtos hidratados."""

    terms: list[SuggestTerm]
    categories: list[SuggestCategory]
    items: list[SearchResultItem]
    query: str


async def _hydrate_page(
    product_reader: ProductReader,
    ids: list[str],
    *,
    auth: AuthContext | None,
    locale: str,
) -> tuple[list[SearchResultItem], dict[str, str]]:
    """Hidrata ids no PostgreSQL (preco/estoque/imagem); compartilhado.

    Descarta entradas defasadas do indice (produto inativo, EPI com CA vencido
    ou ausente do banco). Devolve tambem o mapa ``slug -> nome`` das categorias
    no locale (vazio em pt-BR), usado pelo suggest para traduzir categorias.
    """
    products = await product_reader.get_products_by_ids([uuid.UUID(pid) for pid in ids])
    today = date.today()
    rules_by_product: dict[uuid.UUID, list[CompanyPriceRule]] = {}
    if auth is not None:
        rules_by_product = await product_reader.get_company_price_rules(
            company_id=auth.company_id, product_ids=list(products.keys())
        )
    category_map: dict[str, str] = {}
    if locale != DEFAULT_LOCALE:
        category_map = await product_reader.get_category_name_map(locale)
    items: list[SearchResultItem] = []
    dropped = 0
    for pid_str in ids:
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
        items.append(
            _to_item(
                product,
                auth,
                today,
                rules_by_product.get(product.id, []),
                locale=locale,
                category_map=category_map,
            )
        )
    if dropped:
        _logger.info("search_stale_entries_summary", dropped=dropped, returned=len(items))
    return items, category_map


def _to_item(
    product: ProductRow,
    auth: AuthContext | None,
    today: date,
    rules: list[CompanyPriceRule],
    *,
    locale: str,
    category_map: dict[str, str],
) -> SearchResultItem:
    # Produto bloqueado: preco consultivo (nenhum valor). Visitante de
    # produto vendavel: preco de lista. Autenticado: preco de lista
    # ajustado pelas regras da empresa (negociado > desconto > lista),
    # resolvido aqui (nunca vem do indice ou do vetor).
    sellable = is_sellable(
        status=product.status,
        is_epi=product.is_epi,
        ca_valid_until=product.ca_valid_until,
        today=today,
    )
    if not sellable:
        unit_price: Decimal | None = None
        price_on_request = True
    elif auth is None:
        unit_price = product.base_unit_price
        price_on_request = unit_price is None
    else:
        unit_price = resolve_company_price(
            base_unit_price=product.base_unit_price,
            tiers=[],
            quantity=1,
            category_id=product.category_id,
            rules=rules,
        ).unit_price
        price_on_request = False
    resolved = resolve_product_text(
        source_name=product.name,
        source_description=product.description,
        source_attributes=product.attributes,
        locale=locale,
        translation=product.translations.get(locale) if locale != DEFAULT_LOCALE else None,
    )
    return SearchResultItem(
        id=product.id,
        sku=product.sku,
        name=resolved.name.value or product.name,
        slug=product.slug,
        status=product.status,
        is_epi=product.is_epi,
        ca_status=ca_status(
            is_epi=product.is_epi,
            ca_valid_until=product.ca_valid_until,
            today=today,
        ).value,
        category_id=product.category_id,
        category_name=category_map.get(product.category_slug, product.category_name),
        category_slug=product.category_slug,
        brand_id=product.brand_id,
        brand_name=product.brand_name,
        brand_slug=product.brand_slug,
        base_unit_price=unit_price,
        currency=product.currency,
        min_order_qty=product.min_order_qty,
        price_on_request=price_on_request,
        image_url=resolve_product_image_path(
            product_image_url=product.image_url, category_slug=product.category_slug
        ),
        image_alt=resolve_image_alt(resolved.name.value or product.name),
        content_locale=resolved.content_locale,
    )


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
        # Circuit breaker simples do caminho lexical (Fase 8A).
        self._lexical_failures = 0
        self._lexical_open_until = 0.0

    async def run(self, *, query: SearchQuery, auth: AuthContext | None) -> SearchResultPage:
        self._validate(query)
        started = time.perf_counter()
        ids, total, mode = await self._retrieve(query)
        page_ids = self._paginate(ids, query=query, mode=mode)
        items, _category_map = await _hydrate_page(
            self._product_reader, page_ids, auth=auth, locale=query.locale
        )
        duration = time.perf_counter() - started
        metrics.observe_search(mode=mode, duration=duration)
        _logger.info(
            "search_completed",
            search_mode=mode,
            total=total,
            returned=len(items),
            duration_ms=round(duration * 1000, 2),
        )
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
        breaker_open = time.monotonic() < self._lexical_open_until
        if breaker_open:
            _logger.warning(
                "search_circuit_breaker_open",
                retry_in_seconds=round(self._lexical_open_until - time.monotonic(), 1),
            )
        retrieval_query = (
            replace(query, page=1, page_size=self._settings.embedding_candidate_limit)
            if use_semantic
            else query
        )
        lexical_outcome, semantic_outcome = await asyncio.gather(
            self._run_lexical(retrieval_query, enabled=not breaker_open),
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

    async def _run_lexical(self, query: SearchQuery, *, enabled: bool) -> SearchResult | None:
        if not enabled or self._primary is None:
            return None
        try:
            result = await self._primary.search(query)
        except SearchUnavailableError:
            self._on_lexical_failure()
            raise
        self._on_lexical_success()
        return result

    def _on_lexical_failure(self) -> None:
        """Conta falha e abre o breaker apos N falhas consecutivas (cooldown)."""
        self._lexical_failures += 1
        if self._lexical_failures >= self._settings.search_circuit_breaker_failures:
            cooldown = self._settings.search_circuit_breaker_cooldown_seconds
            self._lexical_open_until = time.monotonic() + cooldown
            _logger.warning(
                "search_circuit_breaker_tripped",
                failures=self._lexical_failures,
                cooldown_seconds=cooldown,
            )

    def _on_lexical_success(self) -> None:
        if self._lexical_failures or self._lexical_open_until:
            _logger.info("search_circuit_breaker_closed")
        self._lexical_failures = 0
        self._lexical_open_until = 0.0

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


def _as_lexical(outcome: SearchResult | BaseException | None) -> tuple[list[str] | None, int]:
    if isinstance(outcome, SearchResult):
        return outcome.ids, outcome.total
    if isinstance(outcome, BaseException):
        _logger.warning("lexical_search_unavailable", error=type(outcome).__name__)
    return None, 0


def _as_semantic(outcome: list[str] | BaseException | None) -> list[str] | None:
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


class SuggestProducts:
    """Sugestoes do dropdown (estilo BestBuy): termos + categorias + produtos.

    Somente lexical (sem pgvector). O motor primario (ES) devolve termos e
    categorias agregadas em UMA consulta; os produtos sao hidratados do
    PostgreSQL pela MESMA rotina do SearchProducts (preco por empresa para
    autenticado, consultivo para visitante; entradas defasadas descartadas).
    """

    def __init__(
        self,
        *,
        primary: SearchReader | None,
        fallback: SearchReader,
        product_reader: ProductReader,
        settings: Settings,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._product_reader = product_reader
        self._settings = settings

    async def run(
        self,
        *,
        q: str,
        auth: AuthContext | None,
        locale: str = DEFAULT_LOCALE,
        term_limit: int = 8,
        category_limit: int = 3,
        product_limit: int = 6,
    ) -> SuggestResult:
        q = q.strip()
        if len(q) < self._settings.search_autocomplete_min_chars:
            return SuggestResult(terms=[], categories=[], items=[], query=q)
        data = await self._retrieve(
            q,
            locale=locale,
            term_limit=term_limit,
            category_limit=category_limit,
            product_limit=product_limit,
        )
        items, category_map = await _hydrate_page(
            self._product_reader,
            data.product_ids[:product_limit],
            auth=auth,
            locale=locale,
        )
        return SuggestResult(
            terms=data.terms,
            categories=self._translate_categories(data.categories, category_map),
            items=items,
            query=q,
        )

    async def _retrieve(
        self,
        q: str,
        *,
        locale: str,
        term_limit: int,
        category_limit: int,
        product_limit: int,
    ) -> SuggestData:
        """Primario (ES); em SearchUnavailableError cai para o fallback Postgres."""
        if self._primary is not None:
            try:
                return await self._primary.suggest(
                    q=q,
                    locale=locale,
                    term_limit=term_limit,
                    category_limit=category_limit,
                    product_limit=product_limit,
                )
            except SearchUnavailableError:
                _logger.warning("suggest_primary_unavailable_switching_to_fallback")
        return await self._fallback.suggest(
            q=q,
            locale=locale,
            term_limit=term_limit,
            category_limit=category_limit,
            product_limit=product_limit,
        )

    def _translate_categories(
        self, categories: list[SuggestCategory], category_map: dict[str, str]
    ) -> list[SuggestCategory]:
        """Troca o nome pelo nome traduzido quando o slug estiver no mapa."""
        if not category_map:
            return categories
        return [
            SuggestCategory(
                name=category_map.get(category.slug, category.name),
                slug=category.slug,
                count=category.count,
            )
            for category in categories
        ]
