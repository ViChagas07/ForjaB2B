"""Ligacao das portas do chat aos modulos existentes (raiz de composicao).

Fica FORA de `app.modules.ai` (bounded contexts): e o unico lugar que conhece
os dois lados. Reusa `SearchProducts` (ranking/ids), o `ProductReader` da busca
(hidratacao com a MESMA resolucao de preco: negociado > desconto > lista) e o
dominio compartilhado (`app.domain.*`). Nenhuma logica de busca e duplicada.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.application.i18n import resolve_product_text
from app.application.ports.tenant import TenantContext
from app.core.logging import get_logger
from app.domain.catalog_image import resolve_image_alt, resolve_product_image_path
from app.domain.pricing import resolve_company_price
from app.domain.product_availability import ca_status, is_sellable
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.application.product_cards import HydratedProduct, ProductCardService
from app.modules.ai.application.tools import (
    CatalogTools,
    ProductSearchResult,
    ToolOrderStatus,
    ToolProduct,
)
from app.modules.search.application.ports import ProductReader, SearchQuery
from app.modules.search.application.search import SearchProducts
from app.wiring.catalog_insights import CatalogInsightsAdapter

_CATEGORY_ID_BY_SLUG = text("SELECT id FROM categories WHERE slug = :slug AND is_active = true")
_logger = get_logger(__name__)
_GENERIC_QUERIES = frozenset(
    {"produto", "produtos", "item", "itens", "coisa", "loja", "catalogo", "catalog"}
)

_SELECT_BUYER_ORDER_STATUS = text(
    "SELECT o.id, o.status, o.created_at, count(oi.id) AS item_count "
    "FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.id "
    "WHERE o.id = CAST(:order_id AS uuid) AND o.company_id = :company_id "
    "AND o.buyer_user_id = :buyer_user_id "
    "GROUP BY o.id, o.status, o.created_at"
)
_LIST_CATEGORIES = text(
    "SELECT c.name, c.slug, count(p.id) FILTER (WHERE p.status = 'ACTIVE') AS total "
    "FROM categories c LEFT JOIN products p ON p.category_id = c.id "
    "WHERE c.is_active = true GROUP BY c.name, c.slug ORDER BY c.name LIMIT 50"
)


class SearchProductsToolAdapter:
    """`ProductSearchPort`/`ProductHydratorPort` sobre o modulo de busca."""

    def __init__(
        self,
        *,
        search_products: SearchProducts,
        product_reader: ProductReader,
        uow_factory: SqlAlchemyUnitOfWorkFactory,
        price_scan_limit: int = 500,
    ) -> None:
        self._search_products = search_products
        self._reader = product_reader
        self._uow_factory = uow_factory
        self._price_scan_limit = max(50, price_scan_limit)

    async def search(
        self,
        *,
        query: str,
        query_pt: str = "",
        query_en: str = "",
        category: str | None,
        limit: int,
        locale: str,
        auth: Any,
        price_sort: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        attributes: Mapping[str, str] | None = None,
        offset: int = 0,
    ) -> ProductSearchResult:
        queries = _normalized_queries(query, query_pt, query_en)
        if len(queries) == 1:
            return await self._search_once(
                query=queries[0],
                category=category,
                limit=limit,
                locale=locale,
                auth=auth,
                price_sort=price_sort,
                price_min=price_min,
                price_max=price_max,
                brand=brand,
                attributes=attributes,
                offset=offset,
            )
        return await self._search_many(
            queries,
            category=category,
            limit=limit,
            locale=locale,
            auth=auth,
            price_sort=price_sort,
            price_min=price_min,
            price_max=price_max,
            brand=brand,
            attributes=attributes,
            offset=offset,
        )

    async def _search_many(
        self,
        queries: list[str],
        *,
        category: str | None,
        limit: int,
        locale: str,
        auth: Any,
        price_sort: str | None,
        price_min: float | None,
        price_max: float | None,
        brand: str | None,
        attributes: Mapping[str, str] | None,
        offset: int,
    ) -> ProductSearchResult:
        per_query_limit = max(offset + limit, 50)
        results = [
            await self._search_once(
                query=item,
                category=category,
                limit=per_query_limit,
                locale=locale,
                auth=auth,
                price_sort=price_sort,
                price_min=price_min,
                price_max=price_max,
                brand=brand,
                attributes=attributes,
                offset=0,
            )
            for item in queries
        ]
        return _merge_search_results(results, offset=offset, limit=limit, price_sort=price_sort)

    async def _search_once(
        self,
        *,
        query: str,
        category: str | None,
        limit: int,
        locale: str,
        auth: Any,
        price_sort: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        brand: str | None = None,
        attributes: Mapping[str, str] | None = None,
        offset: int = 0,
    ) -> ProductSearchResult:
        category_id = await self._category_id(category) if category else None
        price_filtering = any(value is not None for value in (price_sort, price_min, price_max))
        if price_filtering:
            items, capped, _total = await self._scan_price_items(
                query=query,
                category_id=category_id,
                locale=locale,
                auth=auth,
            )
            rows = await self._reader.get_products_by_ids([item.id for item in items])
        else:
            candidate_limit = max(offset + limit, 50) if (brand or attributes) else offset + limit
            page = await self._search_products.run(
                query=SearchQuery(
                    q=_search_text(query),
                    category_id=category_id,
                    brand_id=None,
                    is_epi=None,
                    page=1,
                    page_size=min(candidate_limit, 100),
                    locale=locale,
                ),
                auth=auth,
            )
            items = page.items
            rows = await self._reader.get_products_by_ids([item.id for item in items])
            capped = False
        selected = _select_candidates(
            items,
            rows,
            brand=brand,
            attributes=attributes,
            price_min=price_min,
            price_max=price_max,
            require_price=price_filtering,
        )
        if price_sort in ("asc", "desc"):
            selected.sort(key=lambda pair: _price_sort_key(pair[0], ascending=price_sort == "asc"))
        products = tuple(
            _to_tool_product(item, row) for item, row in selected[offset : offset + limit]
        )
        return ProductSearchResult(products=products, capped=capped)

    async def _scan_price_items(
        self,
        *,
        query: str,
        category_id: uuid.UUID | None,
        locale: str,
        auth: Any,
    ) -> tuple[list[Any], bool, int]:
        """Pagina TODOS os resultados ate `price_scan_limit` (sem N+1 de preco)."""
        items: list[Any] = []
        seen: set[uuid.UUID] = set()
        page_number = 1
        total = 0
        while len(items) < self._price_scan_limit:
            page_size = min(100, self._price_scan_limit - len(items))
            page = await self._search_products.run(
                query=SearchQuery(
                    q=_search_text(query),
                    category_id=category_id,
                    brand_id=None,
                    is_epi=None,
                    page=page_number,
                    page_size=page_size,
                    locale=locale,
                ),
                auth=auth,
            )
            total = page.total
            before = len(items)
            for item in page.items:
                if item.id not in seen:
                    seen.add(item.id)
                    items.append(item)
            if not page.items or len(items) >= total or len(items) == before:
                break
            page_number += 1
        capped = total > len(items)
        if capped:
            _logger.warning(
                "ai_price_scan_capped",
                scanned=len(items),
                cap=self._price_scan_limit,
                total=total,
            )
        return items, capped, total

    async def get(self, *, product_ref: str, locale: str, auth: Any) -> ToolProduct | None:
        product_id = await self._resolve_ref(product_ref, locale=locale, auth=auth)
        if product_id is None:
            return None
        rows = await self._reader.get_products_by_ids([product_id])
        row = rows.get(product_id)
        if row is None or not is_sellable(
            status=row.status,
            is_epi=row.is_epi,
            ca_valid_until=row.ca_valid_until,
            today=date.today(),
        ):
            return None
        resolved = resolve_product_text(
            source_name=row.name,
            source_description=row.description,
            source_attributes=row.attributes,
            locale=locale,
            translation=row.translations.get(locale),
        )
        status = ca_status(
            is_epi=row.is_epi,
            ca_valid_until=row.ca_valid_until,
            today=date.today(),
        )
        hydrated = await self.hydrate(product_ids=[str(row.id)], locale=locale, auth=auth)
        price = hydrated[0].price if hydrated else None
        price_on_request = hydrated[0].price_on_request if hydrated else True
        return ToolProduct(
            product_id=str(row.id),
            name=resolved.name.value or row.name,
            sku=row.sku,
            brand=row.brand_name or "",
            category=row.category_slug,
            attributes=row.attributes,
            description=resolved.description.value or row.description,
            slug=row.slug,
            stock_quantity=row.stock_quantity,
            ca_status=status.value,
            ca_number=row.ca_number,
            min_order_qty=row.min_order_qty,
            price=price,
            price_on_request=price_on_request,
        )

    async def _resolve_ref(self, ref: str, *, locale: str, auth: Any) -> uuid.UUID | None:
        cleaned = ref.strip()
        try:
            return uuid.UUID(cleaned)
        except ValueError:
            pass
        page = await self._search_products.run(
            query=SearchQuery(
                q=cleaned[:100],
                category_id=None,
                brand_id=None,
                is_epi=None,
                page=1,
                page_size=5,
                locale=locale,
            ),
            auth=auth,
        )
        if not page.items:
            return None
        wanted = cleaned.casefold()
        for item in page.items:
            if (
                wanted in {item.sku.casefold(), item.slug.casefold()}
                or wanted in item.name.casefold()
            ):
                return item.id
        return page.items[0].id

    async def hydrate(
        self, *, product_ids: Sequence[str], locale: str, auth: Any
    ) -> list[HydratedProduct]:
        """Hidratacao com a MESMA logica de preco do SearchProducts."""
        parsed = [uuid.UUID(pid) for pid in product_ids]
        rows = await self._reader.get_products_by_ids(parsed)
        rules_by_product = {}
        if auth is not None:
            rules_by_product = await self._reader.get_company_price_rules(
                company_id=auth.company_id, product_ids=list(rows.keys())
            )
        today = date.today()
        hydrated: list[HydratedProduct] = []
        for product_id in parsed:
            row = rows.get(product_id)
            if row is None or not is_sellable(
                status=row.status,
                is_epi=row.is_epi,
                ca_valid_until=row.ca_valid_until,
                today=today,
            ):
                continue
            if auth is None:
                price = row.base_unit_price
                price_on_request = price is None
            else:
                price = resolve_company_price(
                    base_unit_price=row.base_unit_price,
                    tiers=[],
                    quantity=1,
                    category_id=row.category_id,
                    rules=rules_by_product.get(row.id, []),
                ).unit_price
                price_on_request = False
            resolved = resolve_product_text(
                source_name=row.name,
                source_description=row.description,
                source_attributes=row.attributes,
                locale=locale,
                translation=row.translations.get(locale),
            )
            hydrated.append(
                HydratedProduct(
                    product_id=str(row.id),
                    name=resolved.name.value or row.name,
                    sku=row.sku,
                    image_url=resolve_product_image_path(
                        product_image_url=row.image_url, category_slug=row.category_slug
                    ),
                    image_alt=resolve_image_alt(resolved.name.value or row.name),
                    currency=row.currency,
                    min_order_qty=row.min_order_qty,
                    ca_status=ca_status(
                        is_epi=row.is_epi, ca_valid_until=row.ca_valid_until, today=today
                    ).value,
                    price=price,
                    price_on_request=price_on_request,
                )
            )
        return hydrated

    async def _category_id(self, slug: str) -> uuid.UUID | None:
        async with self._uow_factory.begin() as uow:
            row = (await uow.session.execute(_CATEGORY_ID_BY_SLUG, {"slug": slug})).first()
            await uow.commit()
        return row[0] if row else None


class CategoriesAdapter:
    """`CategoriesPort`: nomes traduzidos (quando houver) ou do Postgres."""

    def __init__(
        self, *, product_reader: ProductReader, uow_factory: SqlAlchemyUnitOfWorkFactory
    ) -> None:
        self._reader = product_reader
        self._uow_factory = uow_factory

    async def list_categories(self, *, locale: str) -> list[str]:
        mapped = await self._reader.get_category_name_map(locale)
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_LIST_CATEGORIES)).all()
            await uow.commit()
        return [f"{mapped.get(slug, name)} ({int(total)})" for name, slug, total in rows]


class BuyerOrderStatusAdapter:
    """Status de pedido do PROPRIO usuario (company_id + buyer_user_id da sessao)."""

    def __init__(self, *, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_order_status(
        self, *, order_id: str, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> ToolOrderStatus | None:
        try:
            parsed = uuid.UUID(order_id.strip())
        except ValueError:
            return None
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_BUYER_ORDER_STATUS,
                    {
                        "order_id": str(parsed),
                        "company_id": company_id,
                        "buyer_user_id": user_id,
                    },
                )
            ).first()
            await uow.commit()
        if row is None:
            return None
        return ToolOrderStatus(
            order_id=str(row[0]),
            status=str(row[1]),
            created_at=row[2].isoformat(),
            item_count=int(row[3]),
        )


def build_ai_catalog_wiring(
    *,
    search_products: SearchProducts,
    product_reader: ProductReader,
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    price_scan_limit: int = 500,
    order_status_port: Any | None = None,
) -> tuple[CatalogTools, ProductCardService]:
    """Ferramentas + cartoes prontos para o grafo do chat (FASE 5c/2)."""
    adapter = SearchProductsToolAdapter(
        search_products=search_products,
        product_reader=product_reader,
        uow_factory=uow_factory,
        price_scan_limit=price_scan_limit,
    )
    categories = CategoriesAdapter(product_reader=product_reader, uow_factory=uow_factory)
    orders = order_status_port or BuyerOrderStatusAdapter(uow_factory=uow_factory)
    insights = CatalogInsightsAdapter(
        search_port=adapter,
        hydrator=adapter,
        uow_factory=uow_factory,
        product_reader=product_reader,
    )
    tools = CatalogTools(
        search_port=adapter,
        categories_port=categories,
        order_status_port=orders,
        insights_port=insights,
    )
    cards = ProductCardService(hydrator=adapter)
    return tools, cards


def _brand_matches(row: Any, brand: str) -> bool:
    wanted = brand.strip().lower()
    if not wanted:
        return True
    values = [getattr(row, "brand_name", None), getattr(row, "brand_slug", None)]
    return any(isinstance(value, str) and wanted in value.lower() for value in values)


def _attributes_match(attributes: object, filters: Mapping[str, str]) -> bool:
    if not isinstance(attributes, Mapping):
        return False
    normalized = {
        str(key).strip().lower(): str(value).strip().lower() for key, value in attributes.items()
    }
    for raw_key, raw_value in filters.items():
        wanted_key = raw_key.strip().lower()
        wanted_value = raw_value.strip().lower()
        actual = normalized.get(wanted_key)
        if actual is None or wanted_value not in actual:
            return False
    return True


def _price_sort_key(item: Any, *, ascending: bool) -> tuple[bool, Decimal, str]:
    price = getattr(item, "base_unit_price", None)
    if price is None:
        return (True, Decimal("0"), str(getattr(item, "name", "")))
    return (False, price if ascending else -price, str(getattr(item, "name", "")))


def _normalized_queries(query: str, query_pt: str, query_en: str) -> list[str]:
    """Consulta original + traducao pt/en, sem duplicatas e com limite de 3."""
    result: list[str] = []
    seen: set[str] = set()
    for candidate in (query, query_pt, query_en):
        item = candidate.strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:3] or [query.strip()]


def _merge_search_results(
    results: Sequence[ProductSearchResult],
    *,
    offset: int,
    limit: int,
    price_sort: str | None,
) -> ProductSearchResult:
    merged: list[Any] = []
    seen: set[str] = set()
    for result in results:
        for product in result.products:
            if product.product_id in seen:
                continue
            seen.add(product.product_id)
            merged.append(product)
    if price_sort in ("asc", "desc"):
        merged.sort(
            key=lambda product: _price_sort_key_product(product, ascending=price_sort == "asc")
        )
    return ProductSearchResult(
        products=tuple(merged[offset : offset + limit]),
        capped=any(result.capped for result in results),
    )


def _price_sort_key_product(product: Any, *, ascending: bool) -> tuple[bool, Decimal]:
    price = getattr(product, "price", None)
    if price is None:
        return (True, Decimal("0"))
    return (False, price if ascending else -price)


def _select_candidates(
    items: Sequence[Any],
    rows: Mapping[Any, Any],
    *,
    brand: str | None,
    attributes: Mapping[str, str] | None,
    price_min: float | None,
    price_max: float | None,
    require_price: bool = False,
) -> list[tuple[Any, Any]]:
    selected: list[tuple[Any, Any]] = []
    for item in items:
        row = rows.get(item.id)
        if row is None:
            continue
        if brand and not _brand_matches(row, brand):
            continue
        if attributes and not _attributes_match(row.attributes, attributes):
            continue
        price = getattr(item, "base_unit_price", None)
        if require_price and (price is None or bool(getattr(item, "price_on_request", False))):
            continue
        if price_min is not None and (price is None or price < Decimal(str(price_min))):
            continue
        if price_max is not None and (price is None or price > Decimal(str(price_max))):
            continue
        selected.append((item, row))
    return selected


def _to_tool_product(item: Any, row: Any) -> ToolProduct:
    status = ca_status(
        is_epi=row.is_epi,
        ca_valid_until=row.ca_valid_until,
        today=date.today(),
    )
    return ToolProduct(
        product_id=str(item.id),
        name=item.name,
        sku=item.sku,
        brand=item.brand_name or "",
        category=item.category_slug,
        attributes=row.attributes,
        description=row.description,
        slug=row.slug,
        stock_quantity=row.stock_quantity,
        ca_status=status.value,
        ca_number=row.ca_number,
        min_order_qty=row.min_order_qty,
        price=getattr(item, "base_unit_price", None),
        price_on_request=bool(getattr(item, "price_on_request", False)),
    )


def _search_text(query: str) -> str | None:
    cleaned = query.strip()
    if cleaned.casefold() in _GENERIC_QUERIES:
        return None
    return cleaned[:100]
