"""Portas do contexto de catalogo (contratos de dependencias invertidas).

O catalogo e GLOBAL (sem RLS/company_id): a leitura usa a role de runtime
``forja_app``, que tem apenas SELECT (escrita revogada nas migrations). Os
registros devolvidos sao neutros (nao vazam entidades ORM para a interface).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class CategoryView:
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool


@dataclass(frozen=True, kw_only=True)
class BrandView:
    id: uuid.UUID
    name: str
    slug: str


@dataclass(frozen=True, kw_only=True)
class ProductView:
    id: uuid.UUID
    sku: str
    name: str
    slug: str
    description: str | None
    status: str
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    brand_id: uuid.UUID | None
    brand_name: str | None
    brand_slug: str | None
    is_epi: bool
    ca_number: str | None
    ca_valid_until: date | None
    ca_status: str  # derivado do dominio (nao persistido)
    ncm: str | None
    unit_of_measure: str | None
    weight_kg: Decimal | None
    min_order_qty: int
    base_unit_price: Decimal
    currency: str
    attributes: dict[str, object] | None


@dataclass(frozen=True, kw_only=True)
class ProductFilters:
    """Filtros/ordenacao/paginacao da listagem de produtos (whitelist)."""

    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    status: str | None = None
    is_epi: bool | None = None
    q: str | None = None
    sort: str = "name"
    order: str = "asc"
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, kw_only=True)
class ProductPage:
    items: list[ProductView]
    total: int
    page: int
    page_size: int
    pages: int


class CatalogRepository(Protocol):
    """Persistencia de leitura do catalogo global."""

    async def list_categories(self) -> list[CategoryView]:
        """Lista todas as categorias (ativas e inativas)."""

    async def get_category(self, category_id: uuid.UUID) -> CategoryView | None:
        """Consulta uma categoria."""

    async def list_brands(self) -> list[BrandView]:
        """Lista todas as marcas."""

    async def get_brand(self, brand_id: uuid.UUID) -> BrandView | None:
        """Consulta uma marca."""

    async def list_products(self, filters: ProductFilters) -> ProductPage:
        """Lista produtos paginados com filtros/ordenacao."""

    async def get_product(self, product_id: uuid.UUID) -> ProductView | None:
        """Consulta um produto completo."""
