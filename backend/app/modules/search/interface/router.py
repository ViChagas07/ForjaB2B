"""Endpoints de busca lexical (Fase 4): pesquisa + autocomplete.

O endpoint e publico (como o catalogo), mas aceita autenticacao opcional para
exibir precos. Nenhum preco e resolvido pelo indice: a hidratacao vem do
PostgreSQL.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request

from app.application.security import AuthContext
from app.interface.deps import get_locale, get_optional_auth
from app.modules.search.application.ports import SearchQuery
from app.modules.search.application.search import (
    AutocompleteProducts,
    SearchProducts,
    SearchResultItem,
    SuggestProducts,
)
from app.modules.search.interface.schemas import (
    AutocompleteOut,
    AutocompleteResponse,
    SearchProductBrand,
    SearchProductCategory,
    SearchProductOut,
    SearchQueryParams,
    SearchResponse,
    SuggestCategoryOut,
    SuggestResponse,
    SuggestTermOut,
)

router = APIRouter(prefix="/search", tags=["search"])


def _search_products(request: Request) -> SearchProducts:
    return cast(SearchProducts, request.app.state.search_products)


def _autocomplete_products(request: Request) -> AutocompleteProducts:
    return cast(AutocompleteProducts, request.app.state.search_autocomplete_products)


def _suggest_products(request: Request) -> SuggestProducts:
    return cast(SuggestProducts, request.app.state.search_suggest_products)


def _to_product_out(item: SearchResultItem) -> SearchProductOut:
    return SearchProductOut(
        id=item.id,
        sku=item.sku,
        name=item.name,
        slug=item.slug,
        status=item.status,
        is_epi=item.is_epi,
        ca_status=item.ca_status,
        category=SearchProductCategory(
            id=item.category_id, name=item.category_name, slug=item.category_slug
        ),
        brand=(
            SearchProductBrand(id=item.brand_id, name=item.brand_name, slug=item.brand_slug)
            if item.brand_id is not None
            else None
        ),
        base_unit_price=item.base_unit_price,
        currency=item.currency,
        min_order_qty=item.min_order_qty,
        price_on_request=item.price_on_request,
        image_url=item.image_url,
        image_alt=item.image_alt,
        content_locale=item.content_locale,
    )


@router.get("/products", response_model=SearchResponse)
async def search_products(
    query: Annotated[SearchQueryParams, Query()],
    use_case: Annotated[SearchProducts, Depends(_search_products)],
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    locale: Annotated[str, Depends(get_locale)],
) -> SearchResponse:
    result = await use_case.run(
        query=SearchQuery(
            q=query.q,
            category_id=query.category_id,
            brand_id=query.brand_id,
            is_epi=query.is_epi,
            page=query.page,
            page_size=query.page_size,
            locale=locale,
        ),
        auth=auth,
    )
    return SearchResponse(
        items=[_to_product_out(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
        search_mode=result.search_mode,
    )


@router.get("/products/autocomplete", response_model=AutocompleteResponse)
async def autocomplete_products(
    q: Annotated[str, Query(max_length=100)],
    use_case: Annotated[AutocompleteProducts, Depends(_autocomplete_products)],
) -> AutocompleteResponse:
    suggestions = await use_case.run(q=q)
    return AutocompleteResponse(items=[AutocompleteOut(**vars(s)) for s in suggestions])


@router.get("/suggest", response_model=SuggestResponse)
async def suggest_products(
    q: Annotated[str, Query(max_length=100)],
    use_case: Annotated[SuggestProducts, Depends(_suggest_products)],
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    locale: Annotated[str, Depends(get_locale)],
) -> SuggestResponse:
    """Sugestoes do dropdown: termos, categorias e produtos por score.

    O rate limit e o mesmo de /search/products (middleware classifica
    ``/api/v1/search*``). O preco dos produtos vem do PostgreSQL (lista para
    visitante, por empresa para autenticado); o indice nunca guarda preco.
    """
    result = await use_case.run(q=q, auth=auth, locale=locale)
    return SuggestResponse(
        terms=[SuggestTermOut(text=term.text, kind=term.kind) for term in result.terms],
        categories=[
            SuggestCategoryOut(name=category.name, slug=category.slug, count=category.count)
            for category in result.categories
        ],
        products=[_to_product_out(item) for item in result.items],
        query=result.query,
    )
