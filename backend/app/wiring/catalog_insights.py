# ruff: noqa: S608 - SQL constante; filtros entram por bind params
"""Consultas agregadas do catalogo para o assistente (somente leitura).

Reaproveita a busca existente para termos/ids e o `ProductReader`/hidratacao
para precos por papel (visitante/CPF: tabela publica; CNPJ: preco da empresa).
As agregacoes de marca/categoria usam SQL no PostgreSQL porque o contrato de
busca atual devolve apenas ids/paginas, nao contagens por marca.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import replace
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import text

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.application.product_cards import ProductHydratorPort
from app.modules.ai.application.query_normalization import normalize_query
from app.modules.ai.application.tools import (
    BrandCount,
    BrandListData,
    BrandProductsData,
    BrandResolution,
    CatalogOverviewData,
    CategoryCount,
    PriceRangeData,
    ProductSearchPort,
    ToolProduct,
)
from app.modules.search.application.ports import ProductReader

_SELLABLE = (
    "p.status = 'ACTIVE' AND (p.is_epi = false OR "
    "(p.ca_valid_until IS NOT NULL AND p.ca_valid_until >= CURRENT_DATE))"
)

_BRANDS_ALL = text(
    "SELECT b.name, b.slug, count(p.id)::int AS total "
    "FROM brands AS b JOIN products AS p ON p.brand_id = b.id "
    f"WHERE {_SELLABLE} "
    "GROUP BY b.name, b.slug "
    "ORDER BY total DESC, b.name ASC"
)
_BRANDS_BY_CATEGORY = text(
    "SELECT b.name, b.slug, count(p.id)::int AS total "
    "FROM brands AS b JOIN products AS p ON p.brand_id = b.id "
    "JOIN categories AS c ON c.id = p.category_id "
    f"WHERE c.slug = :category AND {_SELLABLE} "
    "GROUP BY b.name, b.slug "
    "ORDER BY total DESC, b.name ASC"
)
_CATEGORIES = text(
    "SELECT c.name, c.slug, count(p.id)::int AS total "
    "FROM categories AS c JOIN products AS p ON p.category_id = c.id "
    f"WHERE c.is_active = true AND {_SELLABLE} "
    "GROUP BY c.name, c.slug "
    "ORDER BY total DESC, c.name ASC"
)

_BRAND_NORMALIZE = re.compile(r"[^a-z0-9]+")


class CatalogInsightsAdapter:
    """Agregacoes de catalogo com preco resolvido pelo papel da sessao."""

    def __init__(
        self,
        *,
        search_port: ProductSearchPort,
        hydrator: ProductHydratorPort,
        uow_factory: SqlAlchemyUnitOfWorkFactory,
        product_reader: ProductReader,
    ) -> None:
        self._search = search_port
        self._hydrator = hydrator
        self._uow_factory = uow_factory
        self._product_reader = product_reader

    async def resolve_brand(self, *, text: str) -> BrandResolution:
        brands = await self._brand_counts(category=None)
        names = tuple(brand.name for brand in brands[:5])
        wanted = _norm_text(text)
        if not wanted:
            return BrandResolution(matched=None, available=names)
        exact = [brand for brand in brands if _norm_text(brand.name) == wanted]
        if not exact:
            exact = [brand for brand in brands if _norm_text(brand.slug) == wanted]
        if exact:
            return BrandResolution(matched=exact[0], available=names)
        scored: list[tuple[float, BrandCount]] = []
        for brand in brands:
            ratio = max(
                SequenceMatcher(None, wanted, _norm_text(brand.name)).ratio(),
                SequenceMatcher(None, wanted, _norm_text(brand.slug)).ratio(),
            )
            scored.append((ratio, brand))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        if not scored or scored[0][0] < 0.78:
            return BrandResolution(matched=None, available=names)
        top_ratio = scored[0][0]
        close = [
            brand
            for ratio, brand in scored
            if ratio >= max(0.75, top_ratio - 0.05)
        ]
        if len(close) > 1:
            return BrandResolution(
                matched=None, candidates=tuple(close[:3]), available=names
            )
        return BrandResolution(matched=scored[0][1], available=names)

    async def list_brands(
        self,
        *,
        category: str | None,
        query: str | None,
        limit: int,
        locale: str,
        auth: Any,
    ) -> BrandListData:
        cleaned = (query or "").strip()
        if cleaned:
            query_pt, query_en = normalize_query(cleaned)
            result = await self._search.search(
                query=cleaned,
                query_pt=query_pt,
                query_en=query_en,
                category=category,
                limit=100,
                locale=locale,
                auth=auth,
            )
            all_brands = await self._brand_counts(category=None)
            by_name = {_norm_text(brand.name): brand for brand in all_brands}
            counts = Counter(
                product.brand for product in result.products if product.brand.strip()
            )
            brands = tuple(
                BrandCount(
                    name=name,
                    slug=by_name.get(
                        _norm_text(name), BrandCount(name="", slug="", count=0)
                    ).slug,
                    count=count,
                )
                for name, count in counts.most_common()
            )
            total = len(brands)
        else:
            brands = await self._brand_counts(category=category)
            total = len(brands)
        return BrandListData(
            brands=brands[:limit],
            total=total,
            query=cleaned or None,
            category=category,
        )

    async def brand_products(
        self,
        *,
        brand: str,
        category: str | None,
        sort: str | None,
        limit: int,
        locale: str,
        auth: Any,
    ) -> BrandProductsData:
        resolution = await self.resolve_brand(text=brand)
        if resolution.matched is None:
            return BrandProductsData(
                brand=None,
                products=(),
                candidates=resolution.candidates,
                available=resolution.available,
                reason_code=(
                    "brand_ambiguous" if resolution.candidates else "brand_not_found"
                ),
            )
        result = await self._search.search(
            query="",
            query_pt="",
            query_en="",
            category=category,
            limit=limit,
            locale=locale,
            auth=auth,
            price_sort=sort,
            brand=resolution.matched.name,
        )
        return BrandProductsData(
            brand=resolution.matched,
            products=result.products,
            available=resolution.available,
            reason_code=None if result.products else "brand_products_empty",
        )

    async def overview(
        self, *, locale: str, category_query: str | None
    ) -> CatalogOverviewData:
        categories = await self._category_counts()
        name_map = await self._product_reader.get_category_name_map(locale)
        categories = tuple(
            CategoryCount(
                name=name_map.get(item.slug, item.name), slug=item.slug, count=item.count
            )
            for item in categories
        )
        query = (category_query or "").strip()
        if query:
            wanted = _norm_text(query)
            categories = tuple(
                item
                for item in categories
                if wanted in _norm_text(item.name) or wanted in _norm_text(item.slug)
            )
        brand_counts = await self._brand_counts(category=None)
        return CatalogOverviewData(
            categories=categories,
            total_products=sum(item.count for item in categories),
            total_brands=len(brand_counts),
            brand_names=tuple(item.name for item in brand_counts[:10]),
            category_query=query or None,
        )

    async def price_range(
        self,
        *,
        category: str | None,
        query: str | None,
        locale: str,
        auth: Any,
    ) -> PriceRangeData:
        cleaned = (query or "").strip()
        query_pt, query_en = normalize_query(cleaned)
        result = await self._search.search(
            query=cleaned,
            query_pt=query_pt,
            query_en=query_en,
            category=category,
            limit=500,
            locale=locale,
            auth=auth,
        )
        if not result.products:
            return PriceRangeData(min_price=None, max_price=None, count=0)
        hydrated = await self._hydrator.hydrate(
            product_ids=[product.product_id for product in result.products],
            locale=locale,
            auth=auth,
        )
        prices = {
            item.product_id: item.price for item in hydrated if item.price is not None
        }
        priced: list[ToolProduct] = []
        for product in result.products:
            price = prices.get(product.product_id, product.price)
            if price is None:
                continue
            priced.append(replace(product, price=price, price_on_request=False))
        if not priced:
            return PriceRangeData(min_price=None, max_price=None, count=0)
        cheapest = min(priced, key=lambda item: item.price or Decimal("0"))
        priciest = max(priced, key=lambda item: item.price or Decimal("0"))
        return PriceRangeData(
            min_price=cheapest.price,
            max_price=priciest.price,
            count=len(priced),
            min_product=cheapest,
            max_product=priciest,
        )

    async def count_products(
        self,
        *,
        category: str | None,
        brand: str | None,
        query: str | None,
        locale: str,
        auth: Any,
    ) -> int:
        cleaned = (query or "").strip()
        if category:
            resolved_category = await self._resolve_category_slug(category)
            if resolved_category is not None:
                category = resolved_category
            else:
                cleaned = f"{cleaned} {category}".strip()
                category = None
        canonical_brand: str | None = None
        if brand:
            resolution = await self.resolve_brand(text=brand)
            if resolution.matched is None:
                return 0
            canonical_brand = resolution.matched.name
        query_pt, query_en = normalize_query(cleaned)
        result = await self._search.search(
            query=cleaned,
            query_pt=query_pt,
            query_en=query_en,
            category=category,
            limit=500,
            locale=locale,
            auth=auth,
        )
        products = result.products
        if canonical_brand is not None:
            wanted = canonical_brand.casefold()
            products = tuple(
                product for product in products if product.brand.casefold() == wanted
            )
        return len(products)

    async def _resolve_category_slug(self, text: str) -> str | None:
        categories = await self._category_counts()
        wanted = _norm_text(text)
        if not wanted:
            return None
        exact = [
            item
            for item in categories
            if wanted in {_norm_text(item.name), _norm_text(item.slug)}
        ]
        if exact:
            return exact[0].slug
        contains = [
            item
            for item in categories
            if wanted in _norm_text(item.name) or wanted in _norm_text(item.slug)
        ]
        if len(contains) == 1:
            return contains[0].slug
        if contains:
            scored = sorted(
                (
                    (
                        max(
                            SequenceMatcher(None, wanted, _norm_text(item.name)).ratio(),
                            SequenceMatcher(None, wanted, _norm_text(item.slug)).ratio(),
                        ),
                        item,
                    )
                    for item in contains
                ),
                key=lambda pair: pair[0],
            )
            if scored[-1][0] >= 0.82:
                return scored[-1][1].slug
        return None

    async def _brand_counts(self, *, category: str | None) -> tuple[BrandCount, ...]:
        statement = _BRANDS_BY_CATEGORY if category else _BRANDS_ALL
        params = {"category": category} if category else {}
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(statement, params)).all()
        return tuple(
            BrandCount(name=str(row[0]), slug=str(row[1]), count=int(row[2]))
            for row in rows
        )

    async def _category_counts(self) -> tuple[CategoryCount, ...]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_CATEGORIES)).all()
        return tuple(
            CategoryCount(name=str(row[0]), slug=str(row[1]), count=int(row[2]))
            for row in rows
        )


def _norm_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return _BRAND_NORMALIZE.sub("", folded)
