"""Casos de uso de leitura do catalogo global.

Nao ha escrita aqui: o catalogo e mantido pelo backoffice (role forja_admin),
e o runtime apenas le. Cada caso de uso e fino e delega a consulta ao
repositorio, traduzindo ausencia em 404.
"""

from __future__ import annotations

import uuid

from app.modules.catalog.application.errors import (
    BrandNotFoundError,
    CategoryNotFoundError,
    ProductNotFoundError,
)
from app.modules.catalog.application.ports import (
    BrandView,
    CatalogRepository,
    CategoryView,
    ProductFilters,
    ProductPage,
    ProductView,
)


class ListCategories:
    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def list(self) -> list[CategoryView]:
        return await self._repository.list_categories()


class GetCategory:
    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def get(self, category_id: uuid.UUID) -> CategoryView:
        category = await self._repository.get_category(category_id)
        if category is None:
            raise CategoryNotFoundError()
        return category


class ListBrands:
    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def list(self) -> list[BrandView]:
        return await self._repository.list_brands()


class GetBrand:
    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def get(self, brand_id: uuid.UUID) -> BrandView:
        brand = await self._repository.get_brand(brand_id)
        if brand is None:
            raise BrandNotFoundError()
        return brand


class ListProducts:
    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def list(self, filters: ProductFilters) -> ProductPage:
        return await self._repository.list_products(filters)


class GetProduct:
    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def get(self, product_id: uuid.UUID) -> ProductView:
        product = await self._repository.get_product(product_id)
        if product is None:
            raise ProductNotFoundError()
        return product
