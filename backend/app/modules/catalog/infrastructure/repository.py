"""Repositorio SQLAlchemy de leitura do catalogo global.

O catalogo e GLOBAL (sem RLS): a UoW abre sem contexto de tenant e a role
``forja_app`` tem apenas SELECT (escrita revogada nas migrations). Filtros e
ordenacao usam whitelist explicita (sem interpolacao de SQL arbitaria); a busca
textual usa ILIKE parametrizado (sem SQL injection). O ``ca_status`` e derivado
pelo dominio a partir de ``ca_valid_until``, nunca armazenado.
"""

from __future__ import annotations

import math
import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.infrastructure.db.models.catalog import Brand, Category, Product
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.catalog.application.ports import (
    BrandView,
    CategoryView,
    ProductFilters,
    ProductPage,
    ProductView,
)
from app.modules.catalog.domain.availability import ca_status

_SORT_COLUMNS: dict[str, InstrumentedAttribute[Any]] = {
    "name": Product.name,
    "sku": Product.sku,
    "base_unit_price": Product.base_unit_price,
    "created_at": Product.created_at,
}


def _product_conditions(filters: ProductFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.category_id is not None:
        conditions.append(Product.category_id == filters.category_id)
    if filters.brand_id is not None:
        conditions.append(Product.brand_id == filters.brand_id)
    if filters.status is not None:
        conditions.append(Product.status == filters.status)
    if filters.is_epi is not None:
        conditions.append(Product.is_epi == filters.is_epi)
    if filters.q:
        pattern = f"%{filters.q.strip()}%"
        conditions.append(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.description.ilike(pattern),
            )
        )
    return conditions


def _apply_conditions(stmt: Select[Any], conditions: list[ColumnElement[bool]]) -> Select[Any]:
    if conditions:
        stmt = stmt.where(*conditions)
    return stmt


def _product_sort_column(filters: ProductFilters) -> ColumnElement[Any]:
    column = _SORT_COLUMNS.get(filters.sort, Product.name)
    return column.desc() if filters.order == "desc" else column.asc()


class SqlAlchemyCatalogRepository:
    """Implementacao da porta CatalogRepository sobre ORM + UoW."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list_categories(self) -> list[CategoryView]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(select(Category).order_by(Category.name))).scalars()
            await uow.commit()
            return [
                CategoryView(id=c.id, name=c.name, slug=c.slug, is_active=c.is_active) for c in rows
            ]

    async def get_category(self, category_id: uuid.UUID) -> CategoryView | None:
        async with self._uow_factory.begin() as uow:
            category = await uow.session.get(Category, category_id)
            await uow.commit()
            if category is None:
                return None
            return CategoryView(
                id=category.id, name=category.name, slug=category.slug, is_active=category.is_active
            )

    async def list_brands(self) -> list[BrandView]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(select(Brand).order_by(Brand.name))).scalars()
            await uow.commit()
            return [BrandView(id=b.id, name=b.name, slug=b.slug) for b in rows]

    async def get_brand(self, brand_id: uuid.UUID) -> BrandView | None:
        async with self._uow_factory.begin() as uow:
            brand = await uow.session.get(Brand, brand_id)
            await uow.commit()
            if brand is None:
                return None
            return BrandView(id=brand.id, name=brand.name, slug=brand.slug)

    async def list_products(self, filters: ProductFilters) -> ProductPage:
        async with self._uow_factory.begin() as uow:
            conditions = _product_conditions(filters)

            count_stmt = _apply_conditions(select(func.count()).select_from(Product), conditions)
            total = int((await uow.session.execute(count_stmt)).scalar_one())

            stmt = _apply_conditions(
                select(Product, Category.name, Category.slug, Brand.name, Brand.slug)
                .join(Category, Product.category_id == Category.id)
                .outerjoin(Brand, Product.brand_id == Brand.id)
                .order_by(_product_sort_column(filters))
                .limit(filters.page_size)
                .offset((filters.page - 1) * filters.page_size),
                conditions,
            )

            rows = (await uow.session.execute(stmt)).all()
            await uow.commit()

            today = date.today()
            items = [
                self._to_product_view(
                    product, category_name, category_slug, brand_name, brand_slug, today
                )
                for product, category_name, category_slug, brand_name, brand_slug in rows
            ]

            pages = math.ceil(total / filters.page_size) if total else 0
            return ProductPage(
                items=items,
                total=total,
                page=filters.page,
                page_size=filters.page_size,
                pages=pages,
            )

    async def get_product(self, product_id: uuid.UUID) -> ProductView | None:
        async with self._uow_factory.begin() as uow:
            stmt = (
                select(Product, Category.name, Category.slug, Brand.name, Brand.slug)
                .join(Category, Product.category_id == Category.id)
                .outerjoin(Brand, Product.brand_id == Brand.id)
                .where(Product.id == product_id)
            )
            row = (await uow.session.execute(stmt)).first()
            await uow.commit()
            if row is None:
                return None
            product, category_name, category_slug, brand_name, brand_slug = row
            return self._to_product_view(
                product, category_name, category_slug, brand_name, brand_slug, date.today()
            )

    @staticmethod
    def _to_product_view(
        product: Product,
        category_name: str,
        category_slug: str,
        brand_name: str | None,
        brand_slug: str | None,
        today: date,
    ) -> ProductView:
        return ProductView(
            id=product.id,
            sku=product.sku,
            name=product.name,
            slug=product.slug,
            description=product.description,
            status=product.status.value,
            category_id=product.category_id,
            category_name=category_name,
            category_slug=category_slug,
            brand_id=product.brand_id,
            brand_name=brand_name,
            brand_slug=brand_slug,
            is_epi=product.is_epi,
            ca_number=product.ca_number,
            ca_valid_until=product.ca_valid_until,
            ca_status=ca_status(
                is_epi=product.is_epi, ca_valid_until=product.ca_valid_until, today=today
            ).value,
            ncm=product.ncm,
            unit_of_measure=product.unit_of_measure,
            weight_kg=product.weight_kg,
            min_order_qty=product.min_order_qty,
            base_unit_price=product.base_unit_price,
            currency=product.currency,
            attributes=product.attributes,
        )
