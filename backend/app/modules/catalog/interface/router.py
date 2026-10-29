"""Endpoints de leitura do catalogo global.

Somente leitura: nao ha rota de escrita. O catalogo e GLOBAL (compartilhado por
todos os tenants) e publico para leitura; filtros/ordenacao sao validados por
whitelist no schema e mapeados para colunas explicitas no repositorio.
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status

from app.application.security import AuthContext
from app.interface.deps import LocaleInfo, get_locale_info, get_optional_auth
from app.modules.catalog.application.catalog import (
    GetBrand,
    GetCategory,
    GetProduct,
    ListBrands,
    ListCategories,
    ListProducts,
)
from app.modules.catalog.application.ports import ProductFilters, ProductView
from app.modules.catalog.interface.schemas import (
    BrandRef,
    CategoryOut,
    CategoryRef,
    ProductAttributeOut,
    ProductDetail,
    ProductListQuery,
    ProductListResponse,
    ProductSummary,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _list_categories(request: Request) -> ListCategories:
    return cast(ListCategories, request.app.state.catalog_list_categories)


def _get_category(request: Request) -> GetCategory:
    return cast(GetCategory, request.app.state.catalog_get_category)


def _list_brands(request: Request) -> ListBrands:
    return cast(ListBrands, request.app.state.catalog_list_brands)


def _get_brand(request: Request) -> GetBrand:
    return cast(GetBrand, request.app.state.catalog_get_brand)


def _list_products(request: Request) -> ListProducts:
    return cast(ListProducts, request.app.state.catalog_list_products)


def _get_product(request: Request) -> GetProduct:
    return cast(GetProduct, request.app.state.catalog_get_product)


def _to_summary(view: ProductView, language_fallback: bool = False) -> ProductSummary:
    return ProductSummary(
        id=view.id,
        sku=view.sku,
        name=view.name,
        slug=view.slug,
        status=view.status,
        is_epi=view.is_epi,
        ca_status=view.ca_status,
        category=CategoryRef(id=view.category_id, name=view.category_name, slug=view.category_slug),
        brand=(
            BrandRef(id=view.brand_id, name=view.brand_name, slug=view.brand_slug)
            if view.brand_id is not None
            else None
        ),
        base_unit_price=view.base_unit_price,
        currency=view.currency,
        min_order_qty=view.min_order_qty,
        stock_quantity=view.stock_quantity,
        price_on_request=view.price_on_request,
        image_url=view.image_url or "",
        image_alt=view.image_alt,
        content_locale=view.content_locale,
        fallback=view.fallback or language_fallback,
    )


@router.get("/categories", response_model=list[CategoryOut], status_code=status.HTTP_200_OK)
async def list_categories(
    use_case: Annotated[ListCategories, Depends(_list_categories)],
) -> list[CategoryOut]:
    return [CategoryOut(**vars(view)) for view in await use_case.list()]


@router.get("/categories/{category_id}", response_model=CategoryOut, status_code=status.HTTP_200_OK)
async def get_category(
    category_id: uuid.UUID,
    use_case: Annotated[GetCategory, Depends(_get_category)],
) -> CategoryOut:
    return CategoryOut(**vars(await use_case.get(category_id)))


@router.get("/brands", response_model=list[BrandRef], status_code=status.HTTP_200_OK)
async def list_brands(
    use_case: Annotated[ListBrands, Depends(_list_brands)],
) -> list[BrandRef]:
    return [BrandRef(**vars(view)) for view in await use_case.list()]


@router.get("/brands/{brand_id}", response_model=BrandRef, status_code=status.HTTP_200_OK)
async def get_brand(
    brand_id: uuid.UUID,
    use_case: Annotated[GetBrand, Depends(_get_brand)],
) -> BrandRef:
    return BrandRef(**vars(await use_case.get(brand_id)))


@router.get("/products", response_model=ProductListResponse, status_code=status.HTTP_200_OK)
async def list_products(
    query: Annotated[ProductListQuery, Query()],
    use_case: Annotated[ListProducts, Depends(_list_products)],
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    locale_info: Annotated[LocaleInfo, Depends(get_locale_info)],
) -> ProductListResponse:
    page = await use_case.list(
        ProductFilters(
            category_id=query.category_id,
            brand_id=query.brand_id,
            status=query.status.value if query.status is not None else None,
            is_epi=query.is_epi,
            q=query.q,
            sort=query.sort,
            order=query.order,
            page=query.page,
            page_size=query.page_size,
        ),
        company_id=auth.company_id if auth is not None else None,
        locale=locale_info.content_locale,
    )
    return ProductListResponse(
        items=[_to_summary(item, locale_info.content_fallback) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        pages=page.pages,
    )


@router.get("/products/{product_id}", response_model=ProductDetail, status_code=status.HTTP_200_OK)
async def get_product(
    product_id: uuid.UUID,
    use_case: Annotated[GetProduct, Depends(_get_product)],
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    locale_info: Annotated[LocaleInfo, Depends(get_locale_info)],
) -> ProductDetail:
    view = await use_case.get(
        product_id,
        company_id=auth.company_id if auth is not None else None,
        locale=locale_info.content_locale,
    )
    summary = _to_summary(view, locale_info.content_fallback)

    # Converte attributes dict para lista ordenada apenas com atributos preenchidos
    attributes_list: list[ProductAttributeOut] = []
    if view.attributes:
        from app.application.product_attributes import load_default_registry

        registry = load_default_registry()
        category_defs = registry.get_for_category(view.category_slug)
        def_by_key = {d.key: d for d in category_defs}

        for key, value in view.attributes.items():
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            defn = def_by_key.get(key)
            label = defn.label if defn else key
            unit = defn.unit if defn else None
            attributes_list.append(
                ProductAttributeOut(key=key, label=label, value=str(value), unit=unit)
            )

    return ProductDetail(
        **summary.model_dump(),
        description=view.description,
        ca_number=view.ca_number,
        ca_valid_until=view.ca_valid_until,
        ncm=view.ncm,
        unit_of_measure=view.unit_of_measure,
        weight_kg=view.weight_kg,
        attributes=attributes_list,
    )
