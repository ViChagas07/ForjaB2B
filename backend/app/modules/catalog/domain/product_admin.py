"""Domínio puro para administração de produtos (sem frameworks).

Regras de negócio para criação, edição, publicação, despublicação e listagem
de produtos pelo backoffice (papel administrativo).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domain.catalog_image import is_valid_image_url
from app.domain.product_attributes import (
    AttributeRegistry,
    normalize_and_validate_attributes,
    validate_product_required_fields,
)


class ProductAdminError(Exception):
    """Erro base para administração de produtos."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class SkuAlreadyExistsError(ProductAdminError):
    """SKU já cadastrado."""

    def __init__(self, sku: str) -> None:
        super().__init__(f"SKU '{sku}' já existe", code="sku_already_exists")


class SkuImmutableError(ProductAdminError):
    """Tentativa de alterar SKU imutável."""

    def __init__(self) -> None:
        super().__init__("SKU é imutável após a criação", code="sku_immutable")


class SlugAlreadyExistsError(ProductAdminError):
    """Slug já cadastrado."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Slug '{slug}' já existe", code="slug_already_exists")


class OptimisticLockError(ProductAdminError):
    """Conflito de concorrência otimista (versão desatualizada)."""

    def __init__(self) -> None:
        super().__init__(
            "Registro foi alterado por outro usuário; recarregue e tente novamente",
            code="optimistic_lock",
        )


class InvalidImageUrlError(ProductAdminError):
    """URL de imagem inválida."""

    def __init__(self, url: str) -> None:
        super().__init__(
            f"URL de imagem inválida: '{url}'. Use https:// ou /static/...",
            code="invalid_image_url",
        )


class ProductNotFoundError(ProductAdminError):
    """Produto não encontrado."""

    def __init__(self, product_id: uuid.UUID) -> None:
        super().__init__(f"Produto {product_id} não encontrado", code="product_not_found")


class CategoryNotFoundError(ProductAdminError):
    """Categoria não encontrada."""

    def __init__(self, category_id: uuid.UUID) -> None:
        super().__init__(f"Categoria {category_id} não encontrada", code="category_not_found")


class BrandNotFoundError(ProductAdminError):
    """Marca não encontrada."""

    def __init__(self, brand_id: uuid.UUID) -> None:
        super().__init__(f"Marca {brand_id} não encontrada", code="brand_not_found")


@dataclass(frozen=True, kw_only=True)
class ProductAdminView:
    """Visão de produto para administração (com todos os campos)."""

    id: uuid.UUID
    sku: str
    name: str
    slug: str
    description: str | None
    status: str  # "DRAFT" | "ACTIVE" | "ARCHIVED"
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    brand_id: uuid.UUID | None
    brand_name: str | None
    brand_slug: str | None
    is_epi: bool
    ca_number: str | None
    ca_valid_until: str | None  # ISO date string
    ncm: str | None
    unit_of_measure: str | None
    weight_kg: Decimal | None
    min_order_qty: int
    base_unit_price: Decimal
    currency: str
    image_url: str | None
    attributes: dict[str, Any] | None
    version: int  # epoch ms de updated_at para concorrência otimista
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
    stock_quantity: int = 0


@dataclass(frozen=True, kw_only=True)
class ProductListFilters:
    """Filtros para listagem administrativa de produtos."""

    q: str | None = None
    category_id: uuid.UUID | None = None
    status: str | None = None  # "DRAFT" | "ACTIVE" | "ARCHIVED"
    sort: str = "name"
    order: str = "asc"
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, kw_only=True)
class ProductPage:
    """Página de produtos."""

    items: list[ProductAdminView]
    total: int
    page: int
    page_size: int
    pages: int


@dataclass(frozen=True, kw_only=True)
class CreateProductInput:
    """Entrada para criação de produto."""

    sku: str
    name: str
    description: str
    category_id: uuid.UUID
    brand_id: uuid.UUID
    is_epi: bool = False
    ca_number: str | None = None
    ca_valid_until: str | None = None  # ISO date string
    ncm: str | None = None
    unit_of_measure: str | None = None
    weight_kg: Decimal | None = None
    min_order_qty: int = 1
    base_unit_price: Decimal
    currency: str = "BRL"
    image_url: str | None = None
    attributes: dict[str, Any] | None = None
    stock_quantity: int = 0


@dataclass(frozen=True, kw_only=True)
class UpdateProductInput:
    """Entrada para edição de produto (PATCH - campos opcionais)."""

    name: str | None = None
    description: str | None = None
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    is_epi: bool | None = None
    ca_number: str | None = None
    ca_valid_until: str | None = None
    ncm: str | None = None
    unit_of_measure: str | None = None
    weight_kg: Decimal | None = None
    min_order_qty: int | None = None
    base_unit_price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    attributes: dict[str, Any] | None = None
    version: int  # obrigatório para concorrência otimista
    stock_quantity: int | None = None


@dataclass(frozen=True, kw_only=True)
class PublishProductInput:
    """Entrada para publicação/despublicação."""

    version: int  # obrigatório para concorrência otimista


def _generate_slug(name: str) -> str:
    """Gera slug a partir do nome (minúsculas, hyphens, sem acentos)."""
    import unicodedata

    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = slug.lower().strip()
    slug = "".join(c if c.isalnum() else "-" for c in slug)
    slug = "-".join(filter(None, slug.split("-")))
    return slug[:200]


def validate_and_normalize_create_input(
    input_data: CreateProductInput,
    registry: AttributeRegistry,
    existing_skus: set[str],
    existing_slugs: set[str],
) -> tuple[str, dict[str, Any]]:
    """Valida entrada de criação e retorna (slug, attributes_normalizados)."""

    # Valida campos obrigatórios
    errors = validate_product_required_fields(
        input_data.name, input_data.description, str(input_data.brand_id)
    )
    if errors:
        raise ProductAdminError("; ".join(errors), code="validation_error")

    # SKU único
    if input_data.sku in existing_skus:
        raise SkuAlreadyExistsError(input_data.sku)

    # Gera slug único
    slug = _generate_slug(input_data.name)
    base_slug = slug
    counter = 1
    while slug in existing_slugs:
        counter += 1
        slug = f"{base_slug}-{counter}"
        if len(slug) > 200:
            slug = f"{base_slug[:190]}-{counter}"

    # Valida imagem
    if input_data.image_url and not is_valid_image_url(input_data.image_url):
        raise InvalidImageUrlError(input_data.image_url)

    # Valida e normaliza atributos
    normalized_attrs = normalize_and_validate_attributes(
        input_data.attributes,
        registry,
        "",  # category_slug será validado no repositório
    )

    return slug, normalized_attrs


def validate_and_normalize_update_input(
    input_data: UpdateProductInput,
    registry: AttributeRegistry,
    current_category_slug: str,
    current_sku: str,
) -> dict[str, Any] | None:
    """Valida entrada de edição e retorna attributes_normalizados."""

    # Valida imagem se fornecida
    if (
        input_data.image_url is not None
        and input_data.image_url != ""
        and not is_valid_image_url(input_data.image_url)
    ):
        raise InvalidImageUrlError(input_data.image_url)

    # Valida e normaliza atributos se fornecidos
    if input_data.attributes is not None:
        normalized_attrs = normalize_and_validate_attributes(
            input_data.attributes, registry, current_category_slug
        )
        return normalized_attrs

    return None  # sinaliza que atributos não devem ser alterados


def apply_update_to_product(
    product: ProductAdminView,
    input_data: UpdateProductInput,
    normalized_attrs: dict[str, Any] | None,
    registry: AttributeRegistry,
    category_slug: str,
    existing_slugs: set[str] | None = None,
) -> ProductAdminView:
    """Aplica atualização parcial ao produto (retorna nova visão)."""

    # SKU imutável
    if input_data.name is not None:
        # Slug será regenerado se nome mudar
        pass

    # Constrói novo dict de atributos
    new_attributes = dict(product.attributes) if product.attributes else {}
    if normalized_attrs is not None:
        new_attributes = normalized_attrs

    # Gera novo slug se nome mudou (com desambiguação para não colidir)
    new_slug = product.slug
    if input_data.name is not None and input_data.name != product.name:
        new_slug = _generate_slug(input_data.name)
        if existing_slugs is not None:
            base_slug = new_slug
            counter = 1
            while new_slug in existing_slugs and new_slug != product.slug:
                counter += 1
                new_slug = f"{base_slug}-{counter}"
                if len(new_slug) > 200:
                    new_slug = f"{base_slug[:190]}-{counter}"

    return ProductAdminView(
        id=product.id,
        sku=product.sku,
        name=input_data.name if input_data.name is not None else product.name,
        slug=new_slug,
        description=(
            input_data.description if input_data.description is not None else product.description
        ),
        status=product.status,
        category_id=(
            input_data.category_id if input_data.category_id is not None else product.category_id
        ),
        category_name=product.category_name,  # será atualizado pelo repo se category_id mudar
        category_slug=category_slug,
        brand_id=(input_data.brand_id if input_data.brand_id is not None else product.brand_id),
        brand_name=product.brand_name,
        brand_slug=product.brand_slug,
        is_epi=(input_data.is_epi if input_data.is_epi is not None else product.is_epi),
        ca_number=(input_data.ca_number if input_data.ca_number is not None else product.ca_number),
        ca_valid_until=(
            input_data.ca_valid_until
            if input_data.ca_valid_until is not None
            else product.ca_valid_until
        ),
        ncm=input_data.ncm if input_data.ncm is not None else product.ncm,
        unit_of_measure=(
            input_data.unit_of_measure
            if input_data.unit_of_measure is not None
            else product.unit_of_measure
        ),
        weight_kg=(input_data.weight_kg if input_data.weight_kg is not None else product.weight_kg),
        min_order_qty=(
            input_data.min_order_qty
            if input_data.min_order_qty is not None
            else product.min_order_qty
        ),
        stock_quantity=(
            input_data.stock_quantity
            if input_data.stock_quantity is not None
            else product.stock_quantity
        ),
        base_unit_price=(
            input_data.base_unit_price
            if input_data.base_unit_price is not None
            else product.base_unit_price
        ),
        currency=(input_data.currency if input_data.currency is not None else product.currency),
        image_url=(input_data.image_url if input_data.image_url is not None else product.image_url),
        attributes=new_attributes if new_attributes else None,
        version=product.version,
        created_at=product.created_at,
        updated_at=product.updated_at,
        created_by=product.created_by,
        updated_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # placeholder, repo preenche
    )
