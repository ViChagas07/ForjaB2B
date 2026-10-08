"""Schemas HTTP do contexto de catalogo (somente leitura, global)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.domain.enums import ProductStatus

_SORT_FIELDS = Literal["name", "sku", "base_unit_price", "created_at"]
_ORDER = Literal["asc", "desc"]


class CategoryRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    slug: str


class CategoryOut(CategoryRef):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class BrandRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    slug: str


class ProductSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    sku: str
    name: str
    slug: str
    status: str
    is_epi: bool
    ca_status: str
    category: CategoryRef
    brand: BrandRef | None
    base_unit_price: Decimal
    currency: str
    min_order_qty: int


class ProductDetail(ProductSummary):
    model_config = ConfigDict(extra="forbid")

    description: str | None
    ca_number: str | None
    ca_valid_until: date | None
    ncm: str | None
    unit_of_measure: str | None
    weight_kg: Decimal | None
    attributes: dict[str, object] | None


class ProductListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductSummary]
    total: int
    page: int
    page_size: int
    pages: int


class ProductListQuery(BaseModel):
    """Parametros de listagem (filtros + ordenacao + paginacao), whitelist."""

    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    status: ProductStatus | None = None
    is_epi: bool | None = None
    q: str | None = Field(default=None, max_length=100)
    sort: _SORT_FIELDS = "name"
    order: _ORDER = "asc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
