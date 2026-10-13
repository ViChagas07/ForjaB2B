"""Schemas HTTP da API de administração de catálogo (escrita)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Schemas de entrada (request)
# ---------------------------------------------------------------------------


class ProductCreate(BaseModel):
    """Payload para criar produto."""

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    category_id: uuid.UUID
    brand_id: uuid.UUID
    is_epi: bool = False
    ca_number: str | None = Field(default=None, max_length=64)
    ca_valid_until: date | None = None
    ncm: str | None = Field(default=None, max_length=8)
    unit_of_measure: str | None = Field(default=None, max_length=10)
    weight_kg: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    min_order_qty: int = Field(default=1, ge=1)
    base_unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    image_url: str | None = Field(default=None, max_length=500)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "description")
    @classmethod
    def _not_empty_or_spaces(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Campo não pode ser vazio ou apenas espaços")
        return v.strip()

    @field_validator("image_url")
    @classmethod
    def _validate_image_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        from app.domain.catalog_image import is_valid_image_url

        if not is_valid_image_url(v):
            raise ValueError("URL de imagem inválida: use https:// ou /static/...")
        return v


class ProductUpdate(BaseModel):
    """Payload para editar produto (PATCH - todos opcionais exceto version)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    is_epi: bool | None = None
    ca_number: str | None = Field(default=None, max_length=64)
    ca_valid_until: date | None = None
    ncm: str | None = Field(default=None, max_length=8)
    unit_of_measure: str | None = Field(default=None, max_length=10)
    weight_kg: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    min_order_qty: int | None = Field(default=None, ge=1)
    base_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    image_url: str | None = Field(default=None, max_length=500)
    attributes: dict[str, Any] | None = None
    version: int = Field(
        ge=1, description="Versão para concorrência otimista (epoch ms de updated_at)"
    )

    @field_validator("name", "description")
    @classmethod
    def _not_empty_or_spaces(cls, v: str | None) -> str | None:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Campo não pode ser vazio ou apenas espaços")
        return v.strip() if v is not None else None

    @field_validator("image_url")
    @classmethod
    def _validate_image_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        from app.domain.catalog_image import is_valid_image_url

        if not is_valid_image_url(v):
            raise ValueError("URL de imagem inválida: use https:// ou /static/...")
        return v


class ProductPublish(BaseModel):
    """Payload para publicar/despublicar (apenas version)."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(
        ge=1, description="Versão para concorrência otimista (epoch ms de updated_at)"
    )


# ---------------------------------------------------------------------------
# Translation Admin Schemas
# ---------------------------------------------------------------------------


class TranslationUpdate(BaseModel):
    """Payload para editar tradução manualmente."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    attributes: dict[str, Any] | None = None
    mark_reviewed: bool = False


# ---------------------------------------------------------------------------
# Schemas de saída (response)
# ---------------------------------------------------------------------------


class CategoryRefAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    slug: str


class BrandRefAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    slug: str


class ProductAdminSummary(BaseModel):
    """Resumo de produto para listagem administrativa."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    sku: str
    name: str
    slug: str
    status: str
    is_epi: bool
    category: CategoryRefAdmin
    brand: BrandRefAdmin | None
    base_unit_price: Decimal
    currency: str
    image_url: str | None
    version: int
    updated_at: datetime
    updated_by: uuid.UUID


class ProductAdminDetail(ProductAdminSummary):
    """Detalhe completo de produto para administração."""

    model_config = ConfigDict(extra="forbid")

    description: str | None
    ca_number: str | None
    ca_valid_until: date | None
    ncm: str | None
    unit_of_measure: str | None
    weight_kg: Decimal | None
    min_order_qty: int
    attributes: dict[str, Any] | None
    created_at: datetime
    created_by: uuid.UUID


class ProductAdminListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductAdminSummary]
    total: int
    page: int
    page_size: int
    pages: int


class ProductAdminListQuery(BaseModel):
    """Parâmetros de listagem administrativa (filtros + paginação)."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=100)
    category_id: uuid.UUID | None = None
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AttributeDefinitionOut(BaseModel):
    """Definição de atributo para o formulário do admin."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: Literal["text", "number", "enum", "boolean"]
    unit: str | None = None
    options: list[dict[str, str]] | None = None  # [{"key": "...", "label": "..."}]
    scope: list[str]
    section: str
    display_order: int
    required: bool
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    max_length: int | None = None


class StaticImageOut(BaseModel):
    """Imagem estática disponível para seleção."""

    model_config = ConfigDict(extra="forbid")

    path: str
    label: str


# ---------------------------------------------------------------------------
# Translation Admin Response Schemas
# ---------------------------------------------------------------------------


class TranslationAdminOut(BaseModel):
    """Visão administrativa de uma tradução de produto."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    locale: str
    name: str | None
    description: str | None
    attributes: dict[str, Any] | None
    status: str
    source_hash: str
    translated_at: datetime | None
    is_stale: bool


class ProductTranslationsListResponse(BaseModel):
    """Lista de traduções de um produto."""

    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    translations: list[TranslationAdminOut]
