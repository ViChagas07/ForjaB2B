"""Schemas HTTP do contexto de busca (Fase 4)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchProductCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    slug: str


class SearchProductBrand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    slug: str


class SearchProductOut(BaseModel):
    """Produto devolvido pela busca; preco e omitido para visitantes."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    sku: str
    name: str
    slug: str
    status: str
    is_epi: bool
    ca_status: str
    category: SearchProductCategory
    brand: SearchProductBrand | None
    base_unit_price: Decimal | None
    currency: str
    min_order_qty: int
    price_on_request: bool
    image_url: str
    image_alt: str
    content_locale: str


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SearchProductOut]
    total: int
    page: int
    page_size: int
    pages: int
    search_mode: str


class SearchQueryParams(BaseModel):
    """Parametros de busca lexical validados na interface."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=100)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    is_epi: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AutocompleteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    sku: str
    name: str


class AutocompleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AutocompleteOut]


class SuggestTermOut(BaseModel):
    """Termo sugerido pelo dropdown (produto, marca ou SKU)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    kind: Literal["product", "brand", "sku"]


class SuggestCategoryOut(BaseModel):
    """Categoria sugerida, exibida no formato \"em <Categoria>\"."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str
    count: int


class SuggestResponse(BaseModel):
    """Resposta do dropdown de sugestoes (termos + categorias + produtos)."""

    model_config = ConfigDict(extra="forbid")

    terms: list[SuggestTermOut]
    categories: list[SuggestCategoryOut]
    products: list[SearchProductOut]
    query: str
