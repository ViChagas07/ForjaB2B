"""Testes unitarios do suggest do dropdown (autocomplete estilo BestBuy).

Cobre a montagem pura de termos (brand > product > sku, dedupe), o caso de
uso SuggestProducts (minimo de caracteres, fallback, ordem por score, preco
por empresa, traducao de categorias, descarte de defasados) e a estrutura da
DSL enviada ao Elasticsearch (sort por _score, aggs de categoria/marca).
Nao requer servidor ES nem Docker.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest

from app.application.security import AuthContext
from app.core.config import Settings
from app.domain.pricing import CompanyPriceRule
from app.modules.search.application.errors import SearchUnavailableError
from app.modules.search.application.ports import (
    ProductReader,
    ProductRow,
    SearchQuery,
    SearchReader,
    SearchResult,
    SearchSuggestion,
    SuggestCategory,
    SuggestData,
    SuggestTerm,
)
from app.modules.search.application.search import SuggestProducts
from app.modules.search.application.suggest import collect_suggest_terms
from app.modules.search.infrastructure.elasticsearch import ElasticsearchProductIndex


class _FakeSearchReader(SearchReader):
    def __init__(
        self,
        *,
        suggests: dict[str, SuggestData] | None = None,
        fail: bool = False,
    ) -> None:
        self._suggests = suggests or {}
        self._fail = fail
        self.suggest_calls = 0

    async def search(self, query: SearchQuery) -> SearchResult:
        return SearchResult(ids=[], total=0, mode="lexical")

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        return []

    async def suggest(
        self,
        *,
        q: str,
        locale: str,
        term_limit: int,
        category_limit: int,
        product_limit: int,
    ) -> SuggestData:
        self.suggest_calls += 1
        if self._fail:
            raise SearchUnavailableError("elasticsearch down")
        return self._suggests.get(q, SuggestData(terms=[], categories=[], product_ids=[]))


class _FakeProductReader(ProductReader):
    def __init__(
        self,
        rows: list[ProductRow],
        *,
        category_map: dict[str, str] | None = None,
        rules: dict[uuid.UUID, list[CompanyPriceRule]] | None = None,
    ) -> None:
        self._rows = {row.id: row for row in rows}
        self._category_map = category_map or {}
        self._rules = rules or {}

    def iter_products(self, *, batch_size: int) -> AsyncIterator[list[ProductRow]]:
        raise NotImplementedError

    async def get_product(self, product_id: uuid.UUID) -> ProductRow | None:
        return self._rows.get(product_id)

    async def get_products_by_ids(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ProductRow]:
        return {pid: self._rows[pid] for pid in product_ids if pid in self._rows}

    async def get_company_price_rules(
        self, *, company_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[CompanyPriceRule]]:
        return {pid: self._rules.get(pid, []) for pid in product_ids}

    async def get_category_name_map(self, locale: str) -> dict[str, str]:
        return self._category_map


def _settings() -> Settings:
    return Settings(
        search_max_query_length=100,
        search_max_page_size=100,
        search_max_deep_pagination=5000,
        search_autocomplete_min_chars=2,
        search_autocomplete_max_suggestions=10,
    )


def _row(
    key: str,
    *,
    status: str = "ACTIVE",
    base_unit_price: Decimal = Decimal("29.90"),
) -> ProductRow:
    return ProductRow(
        id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        sku=key.upper(),
        name=f"Produto {key}",
        description=None,
        slug=key.lower(),
        status=status,
        is_epi=False,
        ca_number=None,
        ca_valid_until=None,
        category_id=uuid.uuid5(uuid.NAMESPACE_URL, "cat"),
        category_name="Categoria",
        category_slug="categoria",
        brand_id=None,
        brand_name=None,
        brand_slug=None,
        attributes=None,
        image_url=None,
        base_unit_price=base_unit_price,
        currency="BRL",
        min_order_qty=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _auth() -> AuthContext:
    return AuthContext(
        user_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        role="BUYER",
        token_id="tok-1",
    )


def _suggest_use_case(
    *,
    primary: SearchReader,
    fallback: SearchReader,
    rows: list[ProductRow] | None = None,
    category_map: dict[str, str] | None = None,
    rules: dict[uuid.UUID, list[CompanyPriceRule]] | None = None,
) -> SuggestProducts:
    return SuggestProducts(
        primary=primary,
        fallback=fallback,
        product_reader=_FakeProductReader(rows or [], category_map=category_map, rules=rules),
        settings=_settings(),
    )


def test_collect_suggest_terms_ordem_brand_product_sku_e_dedupe() -> None:
    terms = collect_suggest_terms(
        query="cap",
        brands=["Sem Match", "Cappi"],
        product_names=["Capacete JSP", "capacete jsp", "Luva Nitrilica"],
        skus=["EPI-CAP-001", "CAP-9"],
        term_limit=8,
    )
    assert [(term.text, term.kind) for term in terms] == [
        ("Cappi", "brand"),
        ("Capacete JSP", "product"),
        ("Luva Nitrilica", "product"),
        ("CAP-9", "sku"),
    ]


def test_collect_suggest_terms_respeita_limite() -> None:
    terms = collect_suggest_terms(
        query="a",
        brands=[],
        product_names=[f"Produto {indice}" for indice in range(12)],
        skus=[],
        term_limit=8,
    )
    assert len(terms) == 8
    assert all(term.kind == "product" for term in terms)


async def test_suggest_respeita_minimo_de_caracteres() -> None:
    # Ambos os leitores falhariam se chamados; o resultado vazio prova que
    # nenhum deles foi consultado.
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(fail=True), fallback=_FakeSearchReader(fail=True)
    )
    result = await use_case.run(q="a", auth=None)
    assert result.terms == []
    assert result.categories == []
    assert result.items == []
    assert result.query == "a"


async def test_suggest_usa_fallback_quando_es_indisponivel() -> None:
    data = SuggestData(
        terms=[SuggestTerm(text="Capacete", kind="product")],
        categories=[SuggestCategory(name="EPI", slug="epis", count=2)],
        product_ids=[],
    )
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(fail=True),
        fallback=_FakeSearchReader(suggests={"cap": data}),
    )
    result = await use_case.run(q="cap", auth=None)
    assert result.terms == data.terms
    assert result.categories == data.categories
    assert result.items == []


async def test_suggest_preserva_ordem_do_motor_e_preco_de_visitante() -> None:
    primeiro = _row("A", base_unit_price=Decimal("24.90"))
    segundo = _row("B", base_unit_price=Decimal("10.00"))
    data = SuggestData(
        terms=[SuggestTerm(text="Capacete", kind="product")],
        categories=[],
        product_ids=[str(segundo.id), str(primeiro.id)],
    )
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(suggests={"cap": data}),
        fallback=_FakeSearchReader(fail=True),
        rows=[primeiro, segundo],
    )
    result = await use_case.run(q="cap", auth=None)
    assert [item.id for item in result.items] == [segundo.id, primeiro.id]
    assert result.items[0].base_unit_price == Decimal("10.00")
    assert result.items[0].price_on_request is False


async def test_suggest_autenticado_aplica_regra_da_empresa() -> None:
    produto = _row("A", base_unit_price=Decimal("100.00"))
    rules = {
        produto.id: [
            CompanyPriceRule(
                rule_id=uuid.uuid4(),
                rule_type="PERCENT_DISCOUNT",
                percent=Decimal("10"),
            )
        ]
    }
    data = SuggestData(terms=[], categories=[], product_ids=[str(produto.id)])
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(suggests={"cap": data}),
        fallback=_FakeSearchReader(fail=True),
        rows=[produto],
        rules=rules,
    )
    result = await use_case.run(q="cap", auth=_auth())
    assert result.items[0].base_unit_price == Decimal("90.00")
    assert result.items[0].price_on_request is False


async def test_suggest_traduz_categorias_no_locale() -> None:
    data = SuggestData(
        terms=[],
        categories=[SuggestCategory(name="Protecao da Cabeca", slug="protecao-cabeca", count=3)],
        product_ids=[],
    )
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(suggests={"cap": data}),
        fallback=_FakeSearchReader(fail=True),
        category_map={"protecao-cabeca": "Head protection"},
    )
    result = await use_case.run(q="cap", auth=None, locale="en")
    assert result.categories[0].name == "Head protection"
    assert result.categories[0].slug == "protecao-cabeca"


async def test_suggest_descarta_entrada_defasada() -> None:
    inativo = _row("A", status="INACTIVE")
    data = SuggestData(terms=[], categories=[], product_ids=[str(inativo.id)])
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(suggests={"cap": data}),
        fallback=_FakeSearchReader(fail=True),
        rows=[inativo],
    )
    result = await use_case.run(q="cap", auth=None)
    assert result.items == []


async def test_suggest_propaga_erro_quando_ambos_indisponiveis() -> None:
    use_case = _suggest_use_case(
        primary=_FakeSearchReader(fail=True), fallback=_FakeSearchReader(fail=True)
    )
    with pytest.raises(SearchUnavailableError):
        await use_case.run(q="cap", auth=None)


class _CapturingClient:
    """Cliente ES falso: captura kwargs da consulta e devolve resposta fixa."""

    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.search_kwargs: dict[str, Any] | None = None

    def options(self, **kwargs: object) -> _CapturingClient:
        return self

    async def search(self, **kwargs: object) -> dict[str, Any]:
        self.search_kwargs = cast("dict[str, Any]", kwargs)
        return self._response


def _suggest_response() -> dict[str, Any]:
    return {
        "hits": {
            "hits": [
                {
                    "_id": "id-1",
                    "_source": {
                        "id": "id-1",
                        "name": "Capacete JSP",
                        "sku": "EPI-CAP-001",
                        "brand": "Cappi",
                        "category": "Protecao da Cabeca",
                        "category_slug": "protecao-cabeca",
                    },
                },
                {
                    "_id": "id-2",
                    "_source": {
                        "id": "id-2",
                        "name": "Luva Nitrilica",
                        "sku": "CAP-002",
                        "brand": None,
                        "category": "Protecao das Maos",
                        "category_slug": "protecao-maos",
                    },
                },
            ]
        },
        "aggregations": {
            "categories": {
                "buckets": [
                    {
                        "key": "Protecao da Cabeca",
                        "doc_count": 5,
                        "slugs": {"buckets": [{"key": "protecao-cabeca"}]},
                    }
                ]
            },
            "brands": {"buckets": [{"key": "Cappi", "doc_count": 2}]},
        },
    }


async def test_suggest_es_monta_consulta_e_resultado() -> None:
    client = _CapturingClient(_suggest_response())
    index = ElasticsearchProductIndex(client=cast(Any, client), alias="forja_products")
    data = await index.suggest(
        q="cap", locale="pt-BR", term_limit=8, category_limit=3, product_limit=6
    )
    kwargs = client.search_kwargs
    assert kwargs is not None
    assert kwargs["index"] == "forja_products"
    assert kwargs["size"] == 6
    assert kwargs["sort"] == ["_score"]
    assert kwargs["source_includes"] == ["id", "name", "sku", "brand", "category", "category_slug"]
    should = kwargs["query"]["bool"]["must"]["bool"]["should"]
    assert {"match": {"name.autocomplete": {"query": "cap", "boost": 6}}} in should
    assert {
        "match": {"name": {"query": "cap", "fuzziness": "AUTO", "prefix_length": 1, "boost": 2}}
    } in should
    assert {"prefix": {"sku.prefix": {"value": "cap", "boost": 8}}} in should
    assert {"match": {"brand.text": {"query": "cap", "boost": 3}}} in should
    filters = kwargs["query"]["bool"]["filter"]
    assert {"term": {"status": "ACTIVE"}} in filters
    assert {"term": {"is_available": True}} in filters
    assert kwargs["aggs"]["categories"]["terms"] == {"field": "category", "size": 3}
    assert kwargs["aggs"]["categories"]["aggs"]["slugs"]["terms"] == {
        "field": "category_slug",
        "size": 1,
    }
    assert kwargs["aggs"]["brands"]["terms"] == {"field": "brand", "size": 3}
    assert [(term.text, term.kind) for term in data.terms] == [
        ("Cappi", "brand"),
        ("Capacete JSP", "product"),
        ("Luva Nitrilica", "product"),
        ("CAP-002", "sku"),
    ]
    assert data.categories == [
        SuggestCategory(name="Protecao da Cabeca", slug="protecao-cabeca", count=5)
    ]
    assert data.product_ids == ["id-1", "id-2"]


async def test_suggest_es_consulta_campo_do_locale() -> None:
    client = _CapturingClient({"hits": {"hits": []}, "aggregations": {}})
    index = ElasticsearchProductIndex(client=cast(Any, client), alias="forja_products")
    await index.suggest(q="cap", locale="en", term_limit=8, category_limit=3, product_limit=6)
    assert client.search_kwargs is not None
    should = client.search_kwargs["query"]["bool"]["must"]["bool"]["should"]
    assert {"match": {"name_en": {"query": "cap", "boost": 5}}} in should

    await index.suggest(q="cap", locale="pt-BR", term_limit=8, category_limit=3, product_limit=6)
    assert client.search_kwargs is not None
    should_pt = client.search_kwargs["query"]["bool"]["must"]["bool"]["should"]
    assert not any("name_pt-BR" in str(clause) for clause in should_pt)


async def test_suggest_es_sem_texto_retorna_vazio() -> None:
    client = _CapturingClient({"hits": {"hits": []}, "aggregations": {}})
    index = ElasticsearchProductIndex(client=cast(Any, client), alias="forja_products")
    data = await index.suggest(
        q="  ", locale="pt-BR", term_limit=8, category_limit=3, product_limit=6
    )
    assert data.terms == []
    assert data.categories == []
    assert data.product_ids == []
    assert client.search_kwargs is None  # nenhuma consulta enviada
