"""Leitura do catalogo (PostgreSQL) para a sincronizacao do indice de busca.

O catalogo e GLOBAL (sem RLS): a UoW abre sem contexto de tenant e a role de
runtime tem apenas SELECT. A paginacao usa chave (id crescente), estavel e
indexada pela PK, adequada a reindexacao em lotes. Nenhuma escrita.

Usa SQL parametrizado (sem importar o mapeador ORM do catalogo) para preservar
a independencia entre bounded contexts exigida pelo import-linter.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

from sqlalchemy import text

from app.application.i18n import ProductTextTranslation
from app.application.ports.tenant import TenantContext
from app.domain.i18n import DEFAULT_LOCALE
from app.domain.pricing import CompanyPriceRule
from app.infrastructure.db.company_pricing import load_company_price_rules
from app.infrastructure.db.translations import load_product_translations
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.i18n.dictionary import load_category_names
from app.modules.search.application.documents import SEARCH_TRANSLATION_LOCALES
from app.modules.search.application.ports import ProductRow

_NIL_UUID = "00000000-0000-0000-0000-000000000000"

_SELECT_PAGE = text(
    "SELECT p.id, p.sku, p.name, p.description, p.slug, p.status, p.is_epi, "
    "p.ca_number, p.ca_valid_until, p.category_id, c.name AS category_name, "
    "c.slug AS category_slug, p.brand_id, b.name AS brand_name, b.slug AS brand_slug, "
    "p.attributes, p.base_unit_price, p.currency, p.min_order_qty, "
    "p.created_at, p.updated_at, p.image_url "
    "FROM products AS p "
    "JOIN categories AS c ON c.id = p.category_id "
    "LEFT JOIN brands AS b ON b.id = p.brand_id "
    "WHERE p.id > CAST(:last_id AS uuid) ORDER BY p.id LIMIT :batch_size"
)

_SELECT_ONE = text(
    "SELECT p.id, p.sku, p.name, p.description, p.slug, p.status, p.is_epi, "
    "p.ca_number, p.ca_valid_until, p.category_id, c.name AS category_name, "
    "c.slug AS category_slug, p.brand_id, b.name AS brand_name, b.slug AS brand_slug, "
    "p.attributes, p.base_unit_price, p.currency, p.min_order_qty, "
    "p.created_at, p.updated_at, p.image_url "
    "FROM products AS p "
    "JOIN categories AS c ON c.id = p.category_id "
    "LEFT JOIN brands AS b ON b.id = p.brand_id "
    "WHERE p.id = CAST(:product_id AS uuid)"
)

_SELECT_BY_IDS = text(
    "SELECT p.id, p.sku, p.name, p.description, p.slug, p.status, p.is_epi, "
    "p.ca_number, p.ca_valid_until, p.category_id, c.name AS category_name, "
    "c.slug AS category_slug, p.brand_id, b.name AS brand_name, b.slug AS brand_slug, "
    "p.attributes, p.base_unit_price, p.currency, p.min_order_qty, "
    "p.created_at, p.updated_at, p.image_url "
    "FROM products AS p "
    "JOIN categories AS c ON c.id = p.category_id "
    "LEFT JOIN brands AS b ON b.id = p.brand_id "
    "WHERE p.id = ANY(CAST(:product_ids AS uuid[]))"
)


def _to_row(row: Any) -> ProductRow:
    return ProductRow(
        id=row[0],
        sku=row[1],
        name=row[2],
        description=row[3],
        slug=row[4],
        status=row[5],
        is_epi=row[6],
        ca_number=row[7],
        ca_valid_until=row[8],
        category_id=row[9],
        category_name=row[10],
        category_slug=row[11],
        brand_id=row[12],
        brand_name=row[13],
        brand_slug=row[14],
        attributes=row[15],
        base_unit_price=row[16],
        currency=row[17],
        min_order_qty=row[18],
        created_at=row[19],
        updated_at=row[20],
        image_url=row[21],
    )


class SqlAlchemyProductReader:
    """Implementacao da porta ProductReader (somente leitura, global)."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def iter_products(self, *, batch_size: int) -> AsyncIterator[list[ProductRow]]:
        last_id = _NIL_UUID
        while True:
            async with self._uow_factory.begin() as uow:
                rows = (
                    await uow.session.execute(
                        _SELECT_PAGE, {"last_id": last_id, "batch_size": batch_size}
                    )
                ).all()
                base_batch = [_to_row(row) for row in rows]
                translations = await self._translations_for(
                    uow, [product.id for product in base_batch]
                )
                await uow.commit()
            if not base_batch:
                return
            batch = [
                replace(product, translations=translations.get(product.id, {}))
                for product in base_batch
            ]
            last_id = str(batch[-1].id)
            yield batch
            if len(batch) < batch_size:
                return

    async def get_product(self, product_id: uuid.UUID) -> ProductRow | None:
        async with self._uow_factory.begin() as uow:
            row = (await uow.session.execute(_SELECT_ONE, {"product_id": str(product_id)})).first()
            if row is None:
                await uow.commit()
                return None
            product = _to_row(row)
            translations = await self._translations_for(uow, [product.id])
            await uow.commit()
        return replace(product, translations=translations.get(product.id, {}))

    async def get_products_by_ids(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ProductRow]:
        if not product_ids:
            return {}
        async with self._uow_factory.begin() as uow:
            rows = (
                await uow.session.execute(
                    _SELECT_BY_IDS, {"product_ids": [str(pid) for pid in product_ids]}
                )
            ).all()
            products = [_to_row(row) for row in rows]
            translations = await self._translations_for(uow, [product.id for product in products])
            await uow.commit()
        return {
            product.id: replace(product, translations=translations.get(product.id, {}))
            for product in products
        }

    async def _translations_for(
        self, uow: Any, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, ProductTextTranslation]]:
        """Traducoes por idioma (en/es/ar) dos produtos informados."""
        if not product_ids:
            return {}
        rows = await load_product_translations(
            uow.session, product_ids=product_ids, locales=list(SEARCH_TRANSLATION_LOCALES)
        )
        result: dict[uuid.UUID, dict[str, ProductTextTranslation]] = {}
        for (product_id, locale), row in rows.items():
            result.setdefault(product_id, {})[locale] = ProductTextTranslation(
                name=row.name, description=row.description, attributes=row.attributes
            )
        return result

    async def get_category_name_map(self, locale: str) -> dict[str, str]:
        if locale == DEFAULT_LOCALE:
            return {}
        return load_category_names().get(locale, {})

    async def get_company_price_rules(
        self, *, company_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[CompanyPriceRule]]:
        if not product_ids:
            return {}
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            rules = await load_company_price_rules(uow.session, product_ids=product_ids)
            await uow.commit()
        return rules
