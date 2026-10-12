"""Casos de uso de leitura do catalogo global.

Nao ha escrita aqui: o catalogo e mantido pelo backoffice (role forja_admin),
e o runtime apenas le. Cada caso de uso e fino e delega a consulta ao
repositorio, traduzindo ausencia em 404.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from app.application.i18n import ProductTextTranslation, resolve_product_text
from app.domain.catalog_image import resolve_image_alt, resolve_product_image_path
from app.domain.i18n import DEFAULT_LOCALE
from app.domain.pricing import CompanyPriceRule, resolve_company_price
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


def _with_image(view: ProductView) -> ProductView:
    """Resolve a imagem exibida (produto > categoria > generica)."""
    return replace(
        view,
        image_url=resolve_product_image_path(
            product_image_url=view.image_url, category_slug=view.category_slug
        ),
        image_alt=resolve_image_alt(view.name),
    )


def _with_translation(
    view: ProductView,
    *,
    translation: ProductTextTranslation | None,
    category_map: dict[str, str],
    locale: str,
) -> ProductView:
    """Aplica a traducao armazenada (fallback campo a campo para pt-BR)."""
    resolved = resolve_product_text(
        source_name=view.name,
        source_description=view.description,
        source_attributes=view.attributes,
        locale=locale,
        translation=translation,
    )
    return replace(
        view,
        name=resolved.name.value or view.name,
        description=resolved.description.value,
        attributes=resolved.attributes,
        category_name=category_map.get(view.category_slug, view.category_name),
        content_locale=resolved.content_locale,
        fallback=resolved.fallback,
    )


def _mask_price(view: ProductView) -> ProductView:
    """Visitante: preco consultivo (nenhum valor exposto)."""
    return replace(view, base_unit_price=None, price_on_request=True)


def _resolve_price(view: ProductView, rules: list[CompanyPriceRule]) -> ProductView:
    """Autenticado: preco de lista ajustado pelas regras da empresa."""
    base = view.base_unit_price
    if base is None:
        return view
    resolved = resolve_company_price(
        base_unit_price=base,
        tiers=[],
        quantity=1,
        category_id=view.category_id,
        rules=rules,
    )
    return replace(view, base_unit_price=resolved.unit_price, price_on_request=False)


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
    """Lista produtos; resolve o preco por perfil (visitante x empresa)."""

    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def list(
        self,
        filters: ProductFilters,
        *,
        company_id: uuid.UUID | None = None,
        locale: str = DEFAULT_LOCALE,
    ) -> ProductPage:
        page = await self._repository.list_products(filters)
        product_ids = [view.id for view in page.items]
        if company_id is None:
            items = [_with_image(_mask_price(view)) for view in page.items]
        else:
            rules = await self._repository.get_company_price_rules(company_id, product_ids)
            items = [
                _with_image(_resolve_price(view, rules.get(view.id, []))) for view in page.items
            ]
        if locale != DEFAULT_LOCALE:
            translations = await self._repository.get_product_translations(product_ids, locale)
            category_map = await self._repository.get_category_name_map(locale)
            items = [
                _with_translation(
                    view,
                    translation=translations.get(view.id),
                    category_map=category_map,
                    locale=locale,
                )
                for view in items
            ]
        return replace(page, items=items)


class GetProduct:
    """Consulta um produto; resolve o preco por perfil (visitante x empresa)."""

    def __init__(self, *, repository: CatalogRepository) -> None:
        self._repository = repository

    async def get(
        self,
        product_id: uuid.UUID,
        *,
        company_id: uuid.UUID | None = None,
        locale: str = DEFAULT_LOCALE,
    ) -> ProductView:
        product = await self._repository.get_product(product_id)
        if product is None:
            raise ProductNotFoundError()
        if company_id is None:
            view = _with_image(_mask_price(product))
        else:
            rules = await self._repository.get_company_price_rules(company_id, [product_id])
            view = _with_image(_resolve_price(product, rules.get(product_id, [])))
        if locale == DEFAULT_LOCALE:
            return view
        translations = await self._repository.get_product_translations([product_id], locale)
        category_map = await self._repository.get_category_name_map(locale)
        return _with_translation(
            view,
            translation=translations.get(product_id),
            category_map=category_map,
            locale=locale,
        )
