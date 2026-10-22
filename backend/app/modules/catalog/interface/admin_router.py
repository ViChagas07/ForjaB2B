"""Endpoints de administração de catálogo (apenas papel ADMIN da empresa).

- Criação, edição, publicação, despublicação, obtenção e listagem de produtos
- Consulta de definições de atributo por categoria (para formulário)
- Listagem de imagens estáticas disponíveis

Todas as rotas exigem autenticação e papel ADMIN (company admin).
Visitante (sem token) e comprador (role BUYER/APPROVER/FINANCE) recebem 401/403.
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth as get_auth
from app.modules.catalog.application.product_admin import (
    CreateProduct,
    GetAttributeDefinitionsForCategory,
    GetProductAdmin,
    ListProductsAdmin,
    ListStaticImages,
    PublishProduct,
    UnpublishProduct,
    UpdateProduct,
)
from app.modules.catalog.domain.product_admin import ProductAdminView
from app.modules.catalog.interface.admin_schemas import (
    AttributeDefinitionOut,
    BrandRefAdmin,
    CategoryRefAdmin,
    ProductAdminDetail,
    ProductAdminListQuery,
    ProductAdminListResponse,
    ProductAdminSummary,
    ProductCreate,
    ProductPublish,
    ProductUpdate,
    StaticImageOut,
)

router = APIRouter(prefix="/admin/catalog", tags=["catalog-admin"])


# ---------------------------------------------------------------------------
# Dependências para casos de uso
# ---------------------------------------------------------------------------


def _create_product(request: Request) -> CreateProduct:
    return cast(CreateProduct, request.app.state.catalog_admin_create_product)


def _get_product_admin(request: Request) -> GetProductAdmin:
    return cast(GetProductAdmin, request.app.state.catalog_admin_get_product)


def _list_products_admin(request: Request) -> ListProductsAdmin:
    return cast(ListProductsAdmin, request.app.state.catalog_admin_list_products)


def _update_product(request: Request) -> UpdateProduct:
    return cast(UpdateProduct, request.app.state.catalog_admin_update_product)


def _publish_product(request: Request) -> PublishProduct:
    return cast(PublishProduct, request.app.state.catalog_admin_publish_product)


def _unpublish_product(request: Request) -> UnpublishProduct:
    return cast(UnpublishProduct, request.app.state.catalog_admin_unpublish_product)


def _get_attribute_definitions(request: Request) -> GetAttributeDefinitionsForCategory:
    return cast(
        GetAttributeDefinitionsForCategory,
        request.app.state.catalog_admin_get_attribute_definitions,
    )


def _list_static_images(request: Request) -> ListStaticImages:
    return cast(ListStaticImages, request.app.state.catalog_admin_list_static_images)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


@router.post(
    "/products",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Criar produto",
)
async def create_product(
    payload: ProductCreate,
    use_case: Annotated[CreateProduct, Depends(_create_product)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> ProductAdminDetail:
    """Cria um novo produto (ativo por padrão)."""
    from app.modules.catalog.domain.product_admin import CreateProductInput

    input_data = CreateProductInput(
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        category_id=payload.category_id,
        brand_id=payload.brand_id,
        is_epi=payload.is_epi,
        ca_number=payload.ca_number,
        ca_valid_until=(payload.ca_valid_until.isoformat() if payload.ca_valid_until else None),
        ncm=payload.ncm,
        unit_of_measure=payload.unit_of_measure,
        weight_kg=payload.weight_kg,
        min_order_qty=payload.min_order_qty,
        base_unit_price=payload.base_unit_price,
        currency=payload.currency,
        image_url=payload.image_url,
        attributes=payload.attributes,
    )
    product = await use_case.execute(auth, input_data)
    return _to_detail(product)


@router.get(
    "/products/{product_id}",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_200_OK,
    summary="Obter produto (admin)",
)
async def get_product_admin(
    product_id: uuid.UUID,
    use_case: Annotated[GetProductAdmin, Depends(_get_product_admin)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> ProductAdminDetail:
    """Obtém um produto completo para administração."""
    product = await use_case.execute(auth, product_id)
    return _to_detail(product)


@router.get(
    "/products",
    response_model=ProductAdminListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar produtos (admin)",
)
async def list_products_admin(
    query: Annotated[ProductAdminListQuery, Query()],
    use_case: Annotated[ListProductsAdmin, Depends(_list_products_admin)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> ProductAdminListResponse:
    """Lista produtos com filtros e paginação (máx 100 por página)."""
    from app.modules.catalog.domain.product_admin import ProductListFilters

    filters = ProductListFilters(
        q=query.q,
        category_id=query.category_id,
        status=query.status,
        page=query.page,
        page_size=query.page_size,
    )
    page = await use_case.execute(auth, filters)
    return ProductAdminListResponse(
        items=[_to_summary(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        pages=page.pages,
    )


@router.patch(
    "/products/{product_id}",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_200_OK,
    summary="Editar produto (PATCH)",
)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    use_case: Annotated[UpdateProduct, Depends(_update_product)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> ProductAdminDetail:
    """Atualiza campos de um produto (concorrência otimista via version)."""
    from app.modules.catalog.domain.product_admin import UpdateProductInput

    input_data = UpdateProductInput(
        name=payload.name,
        description=payload.description,
        category_id=payload.category_id,
        brand_id=payload.brand_id,
        is_epi=payload.is_epi,
        ca_number=payload.ca_number,
        ca_valid_until=(payload.ca_valid_until.isoformat() if payload.ca_valid_until else None),
        ncm=payload.ncm,
        unit_of_measure=payload.unit_of_measure,
        weight_kg=payload.weight_kg,
        min_order_qty=payload.min_order_qty,
        base_unit_price=payload.base_unit_price,
        currency=payload.currency,
        image_url=payload.image_url,
        attributes=payload.attributes,
        version=payload.version,
    )
    product = await use_case.execute(auth, product_id, input_data)
    return _to_detail(product)


@router.post(
    "/products/{product_id}/publish",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_200_OK,
    summary="Publicar produto (DRAFT -> ACTIVE)",
)
async def publish_product(
    product_id: uuid.UUID,
    payload: ProductPublish,
    use_case: Annotated[PublishProduct, Depends(_publish_product)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> ProductAdminDetail:
    """Publica um produto (torna visível no catálogo público)."""
    from app.modules.catalog.domain.product_admin import PublishProductInput

    input_data = PublishProductInput(version=payload.version)
    product = await use_case.execute(auth, product_id, input_data)
    return _to_detail(product)


@router.post(
    "/products/{product_id}/unpublish",
    response_model=ProductAdminDetail,
    status_code=status.HTTP_200_OK,
    summary="Despublicar produto (ACTIVE -> DRAFT)",
)
async def unpublish_product(
    product_id: uuid.UUID,
    payload: ProductPublish,
    use_case: Annotated[UnpublishProduct, Depends(_unpublish_product)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> ProductAdminDetail:
    """Despublica um produto (remove do catálogo público, volta a rascunho)."""
    from app.modules.catalog.domain.product_admin import PublishProductInput

    input_data = PublishProductInput(version=payload.version)
    product = await use_case.execute(auth, product_id, input_data)
    return _to_detail(product)


@router.get(
    "/categories/{category_slug}/attributes",
    response_model=list[AttributeDefinitionOut],
    status_code=status.HTTP_200_OK,
    summary="Definições de atributo por categoria",
)
async def get_attribute_definitions(
    category_slug: str,
    use_case: Annotated[GetAttributeDefinitionsForCategory, Depends(_get_attribute_definitions)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> list[AttributeDefinitionOut]:
    """Retorna definições de atributo aplicáveis à categoria (para montar formulário)."""
    result = await use_case.execute(category_slug)
    return [AttributeDefinitionOut(**item) for item in result]


@router.get(
    "/static-images",
    response_model=list[StaticImageOut],
    status_code=status.HTTP_200_OK,
    summary="Listar imagens estáticas disponíveis",
)
async def list_static_images(
    use_case: Annotated[ListStaticImages, Depends(_list_static_images)],
    auth: Annotated[AuthContext, Depends(get_auth)],
) -> list[StaticImageOut]:
    """Lista imagens estáticas em /static/catalog/ para seleção no formulário."""
    result = await use_case.execute()
    return [StaticImageOut(**item) for item in result]


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------


def _to_summary(view: ProductAdminView) -> ProductAdminSummary:
    return ProductAdminSummary(
        id=view.id,
        sku=view.sku,
        name=view.name,
        slug=view.slug,
        status=view.status,
        is_epi=view.is_epi,
        category=CategoryRefAdmin(
            id=view.category_id, name=view.category_name, slug=view.category_slug
        ),
        brand=(
            BrandRefAdmin(id=view.brand_id, name=view.brand_name, slug=view.brand_slug)
            if view.brand_id is not None
            else None
        ),
        base_unit_price=view.base_unit_price,
        currency=view.currency,
        image_url=view.image_url,
        version=view.version,
        updated_at=view.updated_at,
        updated_by=view.updated_by,
    )


def _to_detail(view: ProductAdminView) -> ProductAdminDetail:
    summary = _to_summary(view)
    return ProductAdminDetail(
        **summary.model_dump(),
        description=view.description,
        ca_number=view.ca_number,
        ca_valid_until=view.ca_valid_until,
        ncm=view.ncm,
        unit_of_measure=view.unit_of_measure,
        weight_kg=view.weight_kg,
        min_order_qty=view.min_order_qty,
        attributes=view.attributes,
        created_at=view.created_at,
        created_by=view.created_by,
    )
