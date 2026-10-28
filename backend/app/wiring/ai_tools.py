"""Ligacao das portas do chat aos modulos existentes (raiz de composicao).

Fica FORA de `app.modules.ai` (bounded contexts): e o unico lugar que conhece
os dois lados. Reusa `SearchProducts` (ranking/ids), o `ProductReader` da busca
(hidratacao com a MESMA resolucao de preco: negociado > desconto > lista) e o
dominio compartilhado (`app.domain.*`). Nenhuma logica de busca e duplicada.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import text

from app.application.i18n import resolve_product_text
from app.domain.catalog_image import resolve_image_alt, resolve_product_image_path
from app.domain.pricing import resolve_company_price
from app.domain.product_availability import ca_status, is_sellable
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.application.product_cards import HydratedProduct, ProductCardService
from app.modules.ai.application.tools import CatalogTools, ToolProduct
from app.modules.search.application.ports import ProductReader, SearchQuery
from app.modules.search.application.search import SearchProducts

_CATEGORY_ID_BY_SLUG = text("SELECT id FROM categories WHERE slug = :slug AND is_active = true")
_LIST_CATEGORIES = text("SELECT name FROM categories WHERE is_active = true ORDER BY name LIMIT 50")


class SearchProductsToolAdapter:
    """`ProductSearchPort`/`ProductHydratorPort` sobre o modulo de busca."""

    def __init__(
        self,
        *,
        search_products: SearchProducts,
        product_reader: ProductReader,
        uow_factory: SqlAlchemyUnitOfWorkFactory,
    ) -> None:
        self._search_products = search_products
        self._reader = product_reader
        self._uow_factory = uow_factory

    async def search(
        self,
        *,
        query: str,
        category: str | None,
        limit: int,
        locale: str,
        auth: Any,
    ) -> list[ToolProduct]:
        category_id = await self._category_id(category) if category else None
        page = await self._search_products.run(
            query=SearchQuery(
                q=query,
                category_id=category_id,
                brand_id=None,
                is_epi=None,
                page=1,
                page_size=limit,
                locale=locale,
            ),
            auth=auth,
        )
        ids = [item.id for item in page.items]
        rows = await self._reader.get_products_by_ids(ids)
        products: list[ToolProduct] = []
        for item in page.items:
            row = rows.get(item.id)
            if row is None:
                continue
            # SEM preco: ToolProduct carrega so campos de apresentacao.
            products.append(
                ToolProduct(
                    product_id=str(item.id),
                    name=item.name,
                    sku=item.sku,
                    brand=item.brand_name or "",
                    category=item.category_slug,
                    attributes=row.attributes,
                    description=row.description,
                )
            )
        return products

    async def get(self, *, product_id: uuid.UUID, locale: str, auth: Any) -> ToolProduct | None:
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
        return ToolProduct(
            product_id=str(row.id),
            name=resolved.name.value or row.name,
            sku=row.sku,
            brand=row.brand_name or "",
            category=row.category_slug,
            attributes=row.attributes,
            description=row.description,
        )

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
        if mapped:
            return sorted(set(mapped.values()))
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_LIST_CATEGORIES)).all()
            await uow.commit()
        return [row[0] for row in rows]


def build_ai_catalog_wiring(
    *,
    search_products: SearchProducts,
    product_reader: ProductReader,
    uow_factory: SqlAlchemyUnitOfWorkFactory,
) -> tuple[CatalogTools, ProductCardService]:
    """Ferramentas + cartoes prontos para o grafo do chat (FASE 5c)."""
    adapter = SearchProductsToolAdapter(
        search_products=search_products, product_reader=product_reader, uow_factory=uow_factory
    )
    categories = CategoriesAdapter(product_reader=product_reader, uow_factory=uow_factory)
    tools = CatalogTools(search_port=adapter, categories_port=categories)
    cards = ProductCardService(hydrator=adapter)
    return tools, cards
