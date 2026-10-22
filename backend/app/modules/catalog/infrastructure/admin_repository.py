"""Repositório SQLAlchemy de administração do catálogo (escrita com role forja_admin).

A escrita administrativa NÃO usa RLS/tenant: usa a role forja_admin que tem
permissão de escrita nas tabelas globais do catálogo. A UoW é aberta SEM
contexto de tenant.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.infrastructure.db.models.catalog import Brand, Category, Product
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.catalog.application.ports import BrandView, CategoryView
from app.modules.catalog.domain.enums import ProductStatus
from app.modules.catalog.domain.product_admin import (
    ProductAdminView,
    ProductListFilters,
    ProductPage,
)

_SORT_COLUMNS: dict[str, InstrumentedAttribute[Any]] = {
    "name": Product.name,
    "sku": Product.sku,
    "base_unit_price": Product.base_unit_price,
    "created_at": Product.created_at,
}


def _product_admin_conditions(filters: ProductListFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.category_id is not None:
        conditions.append(Product.category_id == filters.category_id)
    if filters.status is not None:
        conditions.append(Product.status == filters.status)
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


def _product_sort_column(filters: ProductListFilters) -> ColumnElement[Any]:
    column = _SORT_COLUMNS.get(filters.sort, Product.name)
    return column.desc() if filters.order == "desc" else column.asc()


class SqlAlchemyCatalogAdminRepository:
    """Implementação da porta CatalogAdminRepository sobre ORM + UoW (sem tenant)."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_all_skus(self) -> set[str]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(select(Product.sku))).scalars().all()
            await uow.commit()
            return set(rows)

    async def get_all_slugs(self) -> set[str]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(select(Product.slug))).scalars().all()
            await uow.commit()
            return set(rows)

    async def get_category(self, category_id: uuid.UUID) -> CategoryView | None:
        async with self._uow_factory.begin() as uow:
            category = await uow.session.get(Category, category_id)
            await uow.commit()
            if category is None:
                return None
            return CategoryView(
                id=category.id,
                name=category.name,
                slug=category.slug,
                is_active=category.is_active,
            )

    async def get_brand(self, brand_id: uuid.UUID) -> BrandView | None:
        async with self._uow_factory.begin() as uow:
            brand = await uow.session.get(Brand, brand_id)
            await uow.commit()
            if brand is None:
                return None
            return BrandView(id=brand.id, name=brand.name, slug=brand.slug)

    async def create(self, product: ProductAdminView) -> ProductAdminView:
        async with self._uow_factory.begin() as uow:
            orm = Product(
                id=product.id,
                sku=product.sku,
                name=product.name,
                slug=product.slug,
                description=product.description,
                status=product.status,
                category_id=product.category_id,
                brand_id=product.brand_id,
                is_epi=product.is_epi,
                ca_number=product.ca_number,
                ca_valid_until=(
                    date.fromisoformat(product.ca_valid_until) if product.ca_valid_until else None
                ),
                ncm=product.ncm,
                unit_of_measure=product.unit_of_measure,
                weight_kg=product.weight_kg,
                min_order_qty=product.min_order_qty,
                base_unit_price=product.base_unit_price,
                currency=product.currency,
                image_url=product.image_url,
                attributes=product.attributes,
            )
            uow.session.add(orm)
            await uow.session.flush()
            await uow.session.refresh(orm, ["category", "brand"])
            await uow.commit()
            return self._to_admin_view(orm, date.today())

    async def get(self, product_id: uuid.UUID) -> ProductAdminView | None:
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
            return self._to_admin_view(
                product, date.today(), category_name, category_slug, brand_name, brand_slug
            )

    async def list(self, filters: ProductListFilters) -> ProductPage:
        async with self._uow_factory.begin() as uow:
            conditions = _product_admin_conditions(filters)

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
                self._to_admin_view(
                    product, today, category_name, category_slug, brand_name, brand_slug
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

    async def update(self, product: ProductAdminView) -> ProductAdminView:
        async with self._uow_factory.begin() as uow:
            current = await uow.session.get(Product, product.id)
            if current is None:
                raise ValueError(f"Produto {product.id} não encontrado")

            current_version = (
                int(current.updated_at.timestamp() * 1000) if current.updated_at else 0
            )
            if product.version != current_version:
                raise ValueError("optimistic_lock")

            current.sku = product.sku
            current.name = product.name
            current.slug = product.slug
            current.description = product.description
            current.status = ProductStatus(product.status)
            current.category_id = product.category_id
            current.brand_id = product.brand_id
            current.is_epi = product.is_epi
            current.ca_number = product.ca_number
            current.ca_valid_until = (
                date.fromisoformat(product.ca_valid_until) if product.ca_valid_until else None
            )
            current.ncm = product.ncm
            current.unit_of_measure = product.unit_of_measure
            current.weight_kg = product.weight_kg
            current.min_order_qty = product.min_order_qty
            current.base_unit_price = product.base_unit_price
            current.currency = product.currency
            current.image_url = product.image_url
            current.attributes = product.attributes
            current.updated_at = datetime.now(UTC)

            await uow.session.flush()
            await uow.session.refresh(current, ["category", "brand"])
            await uow.commit()
            return self._to_admin_view(current, date.today())

    @staticmethod
    def _to_admin_view(
        product: Product,
        today: date,
        category_name: str | None = None,
        category_slug: str | None = None,
        brand_name: str | None = None,
        brand_slug: str | None = None,
    ) -> ProductAdminView:
        if category_name is None:
            category_name = product.category.name if product.category else ""
        if category_slug is None:
            category_slug = product.category.slug if product.category else ""
        if brand_name is None:
            brand_name = product.brand.name if product.brand else None
        if brand_slug is None:
            brand_slug = product.brand.slug if product.brand else None

        return ProductAdminView(
            id=product.id,
            sku=product.sku,
            name=product.name,
            slug=product.slug,
            description=product.description,
            status=product.status,
            category_id=product.category_id,
            category_name=category_name,
            category_slug=category_slug,
            brand_id=product.brand_id,
            brand_name=brand_name,
            brand_slug=brand_slug,
            is_epi=product.is_epi,
            ca_number=product.ca_number,
            ca_valid_until=(product.ca_valid_until.isoformat() if product.ca_valid_until else None),
            ncm=product.ncm,
            unit_of_measure=product.unit_of_measure,
            weight_kg=product.weight_kg,
            min_order_qty=product.min_order_qty,
            base_unit_price=product.base_unit_price,
            currency=product.currency,
            image_url=product.image_url,
            attributes=product.attributes,
            version=int(product.updated_at.timestamp() * 1000) if product.updated_at else 0,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class SqlAlchemySearchOutboxRepository:
    """Implementação da porta SearchOutboxPort sobre UoW (global, sem tenant)."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def emit_upsert(self, *, product_id: uuid.UUID, version: int) -> None:
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO search_outbox (aggregate_id, event_type, version, "
                    "status, attempts, created_at, updated_at) "
                    "VALUES (:aggregate_id, 'UPSERT', :version, 'PENDING', 0, now(), now()) "
                    "ON CONFLICT (aggregate_id, event_type) DO UPDATE SET "
                    "version = GREATEST(search_outbox.version, EXCLUDED.version), "
                    "status = 'PENDING', "
                    "attempts = 0, "
                    "last_error = NULL, "
                    "updated_at = now()"
                ),
                {"aggregate_id": product_id, "version": version},
            )
            await uow.commit()

    async def emit_delete(self, *, product_id: uuid.UUID, version: int) -> None:
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO search_outbox (aggregate_id, event_type, version, "
                    "status, attempts, created_at, updated_at) "
                    "VALUES (:aggregate_id, 'DELETE', :version, 'PENDING', 0, now(), now()) "
                    "ON CONFLICT (aggregate_id, event_type) DO UPDATE SET "
                    "version = GREATEST(search_outbox.version, EXCLUDED.version), "
                    "status = 'PENDING', "
                    "attempts = 0, "
                    "last_error = NULL, "
                    "updated_at = now()"
                ),
                {"aggregate_id": product_id, "version": version},
            )
            await uow.commit()
