"""Politica de exposicao de precos no catalogo publico.

Produtos vendaveis (ativos e, se EPI, com CA valido) expoem o preco de lista.
Produtos bloqueados continuam consultivos e nao vazam o valor persistido.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import cast

from app.application.i18n import ProductTextTranslation
from app.domain.pricing import CompanyPriceRule
from app.modules.catalog.application.catalog import ListProducts
from app.modules.catalog.application.ports import (
    CatalogRepository,
    ProductFilters,
    ProductView,
    PublicProductPage,
)


def _view(
    *,
    status: str = "ACTIVE",
    is_epi: bool = False,
    ca_status: str = "NOT_APPLICABLE",
    ca_valid_until: date | None = None,
    base_unit_price: Decimal | None = Decimal("29.90"),
) -> ProductView:
    return ProductView(
        id=uuid.uuid4(),
        sku="SKU-1",
        name="Produto Teste",
        slug="produto-teste",
        description=None,
        status=status,
        category_id=uuid.uuid4(),
        category_name="Categoria",
        category_slug="categoria",
        brand_id=None,
        brand_name=None,
        brand_slug=None,
        is_epi=is_epi,
        ca_number=None,
        ca_valid_until=ca_valid_until,
        ca_status=ca_status,
        ncm=None,
        unit_of_measure="UN",
        weight_kg=None,
        min_order_qty=1,
        base_unit_price=base_unit_price,
        currency="BRL",
        price_on_request=True,
        image_url=None,
        image_alt="Produto Teste",
        attributes=None,
        content_locale="pt-BR",
        fallback=False,
    )


class _FakeCatalogRepository:
    def __init__(self, view: ProductView, *, rules: list[CompanyPriceRule] | None = None) -> None:
        self._view = view
        self._rules = rules or []

    async def list_products(self, filters: ProductFilters) -> PublicProductPage:
        return PublicProductPage(items=[self._view], total=1, page=1, page_size=20, pages=1)

    async def get_company_price_rules(
        self, company_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[CompanyPriceRule]]:
        return {product_id: self._rules for product_id in product_ids}

    async def get_product_translations(
        self, product_ids: list[uuid.UUID], locale: str
    ) -> dict[uuid.UUID, ProductTextTranslation]:
        return {}

    async def get_category_name_map(self, locale: str) -> dict[str, str]:
        return {}


async def _first_item(
    view: ProductView,
    *,
    company_id: uuid.UUID | None = None,
    rules: list[CompanyPriceRule] | None = None,
) -> ProductView:
    repository = cast(CatalogRepository, _FakeCatalogRepository(view, rules=rules))
    page = await ListProducts(repository=repository).list(
        ProductFilters(), company_id=company_id, locale="pt-BR"
    )
    return page.items[0]


async def test_visitante_ve_preco_de_produto_vendavel() -> None:
    item = await _first_item(_view())
    assert item.price_on_request is False
    assert item.base_unit_price == Decimal("29.90")


async def test_visitante_ve_preco_de_epi_com_ca_valido() -> None:
    item = await _first_item(
        _view(
            is_epi=True,
            ca_status="VALID",
            ca_valid_until=date(2099, 12, 31),
            base_unit_price=Decimal("39.90"),
        )
    )
    assert item.price_on_request is False
    assert item.base_unit_price == Decimal("39.90")


async def test_visitante_nao_ve_preco_de_produto_inativo() -> None:
    item = await _first_item(_view(status="INACTIVE", base_unit_price=Decimal("10.00")))
    assert item.price_on_request is True
    assert item.base_unit_price is None


async def test_visitante_nao_ve_preco_de_epi_vencido() -> None:
    item = await _first_item(
        _view(
            is_epi=True,
            ca_status="EXPIRED",
            ca_valid_until=date(2000, 1, 1),
            base_unit_price=Decimal("8.90"),
        )
    )
    assert item.price_on_request is True
    assert item.base_unit_price is None


async def test_visitante_nao_ve_preco_de_epi_sem_ca() -> None:
    item = await _first_item(
        _view(is_epi=True, ca_status="MISSING", base_unit_price=Decimal("12.50"))
    )
    assert item.price_on_request is True
    assert item.base_unit_price is None


async def test_produto_vendavel_sem_preco_continua_consultivo() -> None:
    item = await _first_item(_view(base_unit_price=None))
    assert item.price_on_request is True
    assert item.base_unit_price is None


async def test_empresa_ve_desconto_em_produto_vendavel() -> None:
    rule = CompanyPriceRule(
        rule_id=uuid.uuid4(),
        rule_type="PERCENT_DISCOUNT",
        percent=Decimal("10"),
    )
    item = await _first_item(
        _view(base_unit_price=Decimal("100.00")),
        company_id=uuid.uuid4(),
        rules=[rule],
    )
    assert item.price_on_request is False
    assert item.base_unit_price == Decimal("90.00")


async def test_empresa_nao_ve_preco_de_produto_bloqueado() -> None:
    rule = CompanyPriceRule(
        rule_id=uuid.uuid4(),
        rule_type="PERCENT_DISCOUNT",
        percent=Decimal("10"),
    )
    item = await _first_item(
        _view(status="INACTIVE", base_unit_price=Decimal("100.00")),
        company_id=uuid.uuid4(),
        rules=[rule],
    )
    assert item.price_on_request is True
    assert item.base_unit_price is None
