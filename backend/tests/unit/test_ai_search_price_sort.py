"""Ordenacao/filtro por preco no adaptador do chat (sem Elasticsearch)."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.wiring.ai_tools import SearchProductsToolAdapter

IDS = [uuid4() for _ in range(3)]


class FakeSearchProducts:
    def __init__(self, items: list[object]) -> None:
        self.items = items
        self.last_query: object | None = None

    async def run(self, *, query: object, auth: object) -> object:
        self.last_query = query
        page = getattr(query, "page", 1)
        size = getattr(query, "page_size", len(self.items))
        start = (page - 1) * size
        return SimpleNamespace(items=self.items[start : start + size], total=len(self.items))


class FakeReader:
    def __init__(self, rows: dict[UUID, object]) -> None:
        self.rows = rows

    async def get_products_by_ids(self, ids: list[UUID]) -> dict[UUID, object]:
        return {product_id: self.rows[product_id] for product_id in ids if product_id in self.rows}


def item(
    product_id: UUID, name: str, price: Decimal | None, *, on_request: bool | None = None
) -> object:
    return SimpleNamespace(
        id=product_id,
        name=name,
        sku=name.upper(),
        brand_name="Marca X",
        category_slug="epi",
        base_unit_price=price,
        price_on_request=(price is None if on_request is None else on_request),
    )


def row(*, brand: str = "Marca X", attributes: dict[str, str] | None = None) -> object:
    return SimpleNamespace(
        brand_name=brand,
        brand_slug=brand.lower().replace(" ", "-"),
        attributes=attributes or {"material": "vaqueta"},
        description="",
        is_epi=False,
        ca_valid_until=None,
        ca_number=None,
        min_order_qty=1,
        stock_quantity=10,
        slug="produto-teste",
    )


def make_adapter(items: list[object], rows: dict[UUID, object]) -> SearchProductsToolAdapter:
    return SearchProductsToolAdapter(
        search_products=FakeSearchProducts(items),  # type: ignore[arg-type]
        product_reader=FakeReader(rows),  # type: ignore[arg-type]
        uow_factory=None,  # type: ignore[arg-type]
    )


async def test_price_sort_asc_coloca_mais_barato_primeiro() -> None:
    items = [
        item(IDS[0], "Luva C", Decimal("30")),
        item(IDS[1], "Luva A", Decimal("10")),
        item(IDS[2], "Luva B", Decimal("20")),
    ]
    adapter = make_adapter(items, {pid: row() for pid in IDS})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=3,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
    )
    assert [product.name for product in result.products] == ["Luva A", "Luva B", "Luva C"]


async def test_price_sort_desc_coloca_mais_caro_primeiro() -> None:
    items = [
        item(IDS[0], "Luva C", Decimal("30")),
        item(IDS[1], "Luva A", Decimal("10")),
        item(IDS[2], "Luva B", Decimal("20")),
    ]
    adapter = make_adapter(items, {pid: row() for pid in IDS})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=3,
        locale="pt-BR",
        auth=None,
        price_sort="desc",
    )
    assert [product.name for product in result.products] == ["Luva C", "Luva B", "Luva A"]


async def test_price_max_filtra_e_mantem_sem_preco_fora() -> None:
    items = [
        item(IDS[0], "Luva C", Decimal("30")),
        item(IDS[1], "Luva A", Decimal("10")),
        item(IDS[2], "Luva B", None),
    ]
    adapter = make_adapter(items, {pid: row() for pid in IDS})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=3,
        locale="pt-BR",
        auth=None,
        price_max=15,
    )
    assert [product.name for product in result.products] == ["Luva A"]


async def test_brand_e_atributos_filtram_no_codigo() -> None:
    items = [
        item(IDS[0], "Luva X", Decimal("10")),
        item(IDS[1], "Luva Y", Decimal("20")),
    ]
    rows = {
        IDS[0]: row(brand="Marca X", attributes={"material": "vaqueta"}),
        IDS[1]: row(brand="Marca Y", attributes={"material": "nitrilo"}),
    }
    adapter = make_adapter(items, rows)
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=5,
        locale="pt-BR",
        auth=None,
        brand="Marca X",
        attributes={"material": "vaqueta"},
    )
    assert [product.name for product in result.products] == ["Luva X"]


async def test_sem_preco_sob_consulta_e_excluido_da_ordenacao() -> None:
    items = [
        item(IDS[0], "Luva Sob Consulta", None),
        item(IDS[1], "Luva A", Decimal("10")),
    ]
    adapter = make_adapter(items, {pid: row() for pid in IDS})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=2,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
    )
    assert [product.name for product in result.products] == ["Luva A"]


async def test_mais_barato_fora_dos_50_primeiros_aparece_com_asc() -> None:
    items = [item(uuid4(), f"Luva {index:03d}", Decimal(str(100 + index))) for index in range(120)]
    # O mais barato tem a PIOR relevancia (ultimo da lista).
    items.append(item(IDS[0], "Luva Mais Barata", Decimal("1.00")))
    rows = {item.id: row() for item in items}
    adapter = make_adapter(items, rows)
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=3,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
    )
    assert result.products[0].name == "Luva Mais Barata"


async def test_teto_de_varredura_marca_capped() -> None:
    items = [item(uuid4(), f"Luva {index:03d}", Decimal(str(100 + index))) for index in range(120)]
    adapter = make_adapter(items, {item.id: row() for item in items})
    # Reduz o teto para 60 para exercitar o cap sem criar 500 itens.
    adapter._price_scan_limit = 60
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=3,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
    )
    assert result.capped is True


async def test_offset_avanca_resultados_em_preco_asc() -> None:
    items = [item(uuid4(), f"Luva {index}", Decimal(str(10 + index * 10))) for index in range(5)]
    adapter = make_adapter(items, {item.id: row() for item in items})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=2,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
        offset=2,
    )
    assert [product.name for product in result.products] == ["Luva 2", "Luva 3"]


async def test_offset_avanca_resultados_sem_ordenacao() -> None:
    items = [item(uuid4(), f"Luva {index}", Decimal(str(10 + index * 10))) for index in range(5)]
    adapter = make_adapter(items, {item.id: row() for item in items})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=2,
        locale="pt-BR",
        auth=None,
        offset=2,
    )
    assert [product.name for product in result.products] == ["Luva 2", "Luva 3"]


async def test_produto_sob_consulta_com_preco_interno_e_excluido() -> None:
    items = [
        item(IDS[0], "Luva Sob Consulta", Decimal("5"), on_request=True),
        item(IDS[1], "Luva Com Preco", Decimal("10")),
    ]
    adapter = make_adapter(items, {pid: row() for pid in IDS})
    result = await adapter.search(
        query="luvas",
        category=None,
        limit=2,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
    )
    assert [product.name for product in result.products] == ["Luva Com Preco"]


async def test_consulta_generica_de_produto_usa_busca_ampla() -> None:
    items = [item(IDS[0], "Luva A", Decimal("10"))]
    search = FakeSearchProducts(items)
    adapter = SearchProductsToolAdapter(
        search_products=search,  # type: ignore[arg-type]
        product_reader=FakeReader({IDS[0]: row()}),  # type: ignore[arg-type]
        uow_factory=None,  # type: ignore[arg-type]
    )
    result = await adapter.search(
        query="produto",
        category=None,
        limit=1,
        locale="pt-BR",
        auth=None,
        price_sort="asc",
    )
    assert result.products[0].name == "Luva A"
    assert getattr(search.last_query, "q", "missing") is None
