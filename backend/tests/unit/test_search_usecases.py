"""Testes unitarios dos casos de uso de busca (Fase 4) com leitores falsos."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.application.security import AuthContext
from app.core.config import Settings
from app.domain.pricing import CompanyPriceRule
from app.modules.search.application.errors import InvalidSearchQueryError, SearchUnavailableError
from app.modules.search.application.ports import (
    ProductReader,
    ProductRow,
    SearchQuery,
    SearchReader,
    SearchResult,
    SearchSuggestion,
)
from app.modules.search.application.search import AutocompleteProducts, SearchProducts


class _FakeSearchReader(SearchReader):
    def __init__(
        self,
        results: dict[str, SearchResult] | None = None,
        suggestions: dict[str, list[SearchSuggestion]] | None = None,
        fail: bool = False,
    ) -> None:
        self._results = results or {}
        self._suggestions = suggestions or {}
        self._fail = fail

    async def search(self, query: SearchQuery) -> SearchResult:
        if self._fail:
            raise SearchUnavailableError("elasticsearch down")
        key = (query.q or "").strip()
        return self._results.get(key, SearchResult(ids=[], total=0, mode="lexical"))

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        if self._fail:
            raise SearchUnavailableError("elasticsearch down")
        return self._suggestions.get(q, [])


class _FakeProductReader(ProductReader):
    def __init__(
        self,
        rows: list[ProductRow],
        rules: dict[uuid.UUID, list[CompanyPriceRule]] | None = None,
    ) -> None:
        self._rows = {row.id: row for row in rows}
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
    is_epi: bool = False,
    ca_valid_until: date | None = None,
    base_unit_price: Decimal = Decimal("29.90"),
) -> ProductRow:
    return ProductRow(
        id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        sku=key.upper(),
        name=f"Produto {key}",
        description=None,
        slug=key.lower(),
        status=status,
        is_epi=is_epi,
        ca_number=None,
        ca_valid_until=ca_valid_until,
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
        token_id="tok-1",  # noqa: S106 - identificador de token de teste, nao segredo
    )


async def test_search_hidrata_e_mascara_preco_para_visitante() -> None:
    a = _row("A")
    b = _row("B")
    ids = [str(a.id), str(b.id)]
    primary = _FakeSearchReader({"": SearchResult(ids=ids, total=2, mode="lexical")})
    fallback = _FakeSearchReader()
    use_case = SearchProducts(
        primary=primary,
        fallback=fallback,
        semantic=None,
        product_reader=_FakeProductReader([a, b]),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q=None, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=None,
    )
    assert result.search_mode == "lexical"
    assert len(result.items) == 2
    assert all(item.price_on_request for item in result.items)
    assert all(item.base_unit_price is None for item in result.items)


async def test_search_autenticado_exibe_preco_base() -> None:
    a = _row("A", base_unit_price=Decimal("49.90"))
    primary = _FakeSearchReader(
        {"capacete": SearchResult(ids=[str(a.id)], total=1, mode="lexical")}
    )
    use_case = SearchProducts(
        primary=primary,
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([a]),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q="capacete", category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=_auth(),
    )
    assert result.items[0].price_on_request is False
    assert result.items[0].base_unit_price == Decimal("49.90")


async def test_search_fallback_quando_es_indisponivel() -> None:
    a = _row("A")
    primary = _FakeSearchReader(fail=True)
    fallback = _FakeSearchReader(
        {"luva": SearchResult(ids=[str(a.id)], total=1, mode="postgres_fallback")}
    )
    use_case = SearchProducts(
        primary=primary,
        fallback=fallback,
        semantic=None,
        product_reader=_FakeProductReader([a]),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q="luva", category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=None,
    )
    assert result.search_mode == "postgres_fallback"
    assert len(result.items) == 1


async def test_search_ambos_motores_indisponiveis_propaga_erro() -> None:
    use_case = SearchProducts(
        primary=_FakeSearchReader(fail=True),
        fallback=_FakeSearchReader(fail=True),
        semantic=None,
        product_reader=_FakeProductReader([]),
        settings=_settings(),
    )
    with pytest.raises(SearchUnavailableError):
        await use_case.run(
            query=SearchQuery(
                q="x", category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
            ),
            auth=None,
        )


async def test_search_descarta_entrada_defasada_do_indice() -> None:
    a = _row("A", status="INACTIVE")
    primary = _FakeSearchReader({"": SearchResult(ids=[str(a.id)], total=1, mode="lexical")})
    use_case = SearchProducts(
        primary=primary,
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([a]),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q=None, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=None,
    )
    assert result.items == []


async def test_search_valida_paginacao_profunda() -> None:
    use_case = SearchProducts(
        primary=_FakeSearchReader(),
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([]),
        settings=_settings(),
    )
    with pytest.raises(InvalidSearchQueryError):
        await use_case.run(
            query=SearchQuery(
                q=None, category_id=None, brand_id=None, is_epi=None, page=1000, page_size=20
            ),
            auth=None,
        )


async def test_search_valida_tamanho_do_texto() -> None:
    use_case = SearchProducts(
        primary=_FakeSearchReader(),
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([]),
        settings=_settings(),
    )
    with pytest.raises(InvalidSearchQueryError):
        await use_case.run(
            query=SearchQuery(
                q="x" * 101, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
            ),
            auth=None,
        )


async def test_autocomplete_respeita_tamanho_minimo() -> None:
    use_case = AutocompleteProducts(
        primary=_FakeSearchReader(),
        fallback=_FakeSearchReader(),
        settings=_settings(),
    )
    result = await use_case.run(q="a")
    assert result == []


async def test_autocomplete_usa_fallback_quando_es_indisponivel() -> None:
    suggestion = SearchSuggestion(id=str(uuid.uuid4()), sku="CAP-001", name="Capacete")
    primary = _FakeSearchReader(fail=True)
    fallback = _FakeSearchReader(suggestions={"cap": [suggestion]})
    use_case = AutocompleteProducts(primary=primary, fallback=fallback, settings=_settings())
    result = await use_case.run(q="cap")
    assert result == [suggestion]


async def test_search_aplica_desconto_da_empresa() -> None:
    a = _row("A", base_unit_price=Decimal("100.00"))
    rules = {
        a.id: [
            CompanyPriceRule(
                rule_id=uuid.uuid4(),
                rule_type="PERCENT_DISCOUNT",
                percent=Decimal("10"),
            )
        ]
    }
    primary = _FakeSearchReader({"luva": SearchResult(ids=[str(a.id)], total=1, mode="lexical")})
    use_case = SearchProducts(
        primary=primary,
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([a], rules=rules),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q="luva", category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=_auth(),
    )
    assert result.items[0].price_on_request is False
    assert result.items[0].base_unit_price == Decimal("90.00")


async def test_search_preco_negociado_vence_o_desconto() -> None:
    a = _row("A", base_unit_price=Decimal("100.00"))
    rules = {
        a.id: [
            CompanyPriceRule(
                rule_id=uuid.uuid4(),
                rule_type="PERCENT_DISCOUNT",
                percent=Decimal("10"),
            ),
            CompanyPriceRule(
                rule_id=uuid.uuid4(),
                rule_type="FIXED_PRICE",
                product_id=a.id,
                unit_price=Decimal("77.50"),
            ),
        ]
    }
    primary = _FakeSearchReader({"luva": SearchResult(ids=[str(a.id)], total=1, mode="lexical")})
    use_case = SearchProducts(
        primary=primary,
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([a], rules=rules),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q="luva", category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=_auth(),
    )
    assert result.items[0].base_unit_price == Decimal("77.50")


async def test_search_preserva_ordem_retornada_pelo_motor() -> None:
    a = _row("A")
    b = _row("B")
    primary = _FakeSearchReader(
        {"": SearchResult(ids=[str(b.id), str(a.id)], total=2, mode="lexical")}
    )
    use_case = SearchProducts(
        primary=primary,
        fallback=_FakeSearchReader(),
        semantic=None,
        product_reader=_FakeProductReader([a, b]),
        settings=_settings(),
    )
    result = await use_case.run(
        query=SearchQuery(
            q=None, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20
        ),
        auth=None,
    )
    assert [item.id for item in result.items] == [b.id, a.id]
