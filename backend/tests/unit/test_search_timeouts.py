"""Testes A1 (Fase 8A): timeouts por uso e circuit breaker do caminho lexical."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

from app.core.config import Settings
from app.domain.pricing import CompanyPriceRule
from app.modules.search.application.errors import SearchUnavailableError
from app.modules.search.application.ports import (
    ProductRow,
    SearchQuery,
    SearchResult,
    SearchSuggestion,
)
from app.modules.search.application.search import SearchProducts
from app.modules.search.infrastructure import elasticsearch as es_mod

_QUERY = SearchQuery(
    q="capacete", category_id=None, brand_id=None, is_epi=None, page=1, page_size=10
)


class _FakeClient:
    """Registra as opcoes por chamada e devolve hits vazios."""

    def __init__(self) -> None:
        self.options_kwargs: dict[str, object] | None = None
        self.search_kwargs: dict[str, object] | None = None

    def options(self, **kwargs: object) -> _FakeClient:
        self.options_kwargs = kwargs
        return self

    async def search(self, **kwargs: object) -> dict[str, object]:
        self.search_kwargs = kwargs
        return {"hits": {"total": {"value": 0}, "hits": []}}


class _FlakyPrimary:
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.calls = 0

    async def search(self, query: SearchQuery) -> SearchResult:
        self.calls += 1
        if self.fail:
            raise SearchUnavailableError("down")
        return SearchResult(ids=[], total=0, mode="lexical")

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        return []


class _Fallback:
    async def search(self, query: SearchQuery) -> SearchResult:
        return SearchResult(ids=[], total=0, mode="postgres_fallback")

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        return []


class _EmptyReader:
    def iter_products(self, *, batch_size: int) -> AsyncIterator[list[ProductRow]]:
        raise NotImplementedError

    async def get_product(self, product_id: uuid.UUID) -> ProductRow | None:
        return None

    async def get_products_by_ids(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ProductRow]:
        return {}

    async def get_company_price_rules(
        self, *, company_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[CompanyPriceRule]]:
        return {}

    async def get_category_name_map(self, locale: str) -> dict[str, str]:
        return {}


def test_defaults_de_timeout_de_busca_e_indexacao() -> None:
    settings = Settings()
    assert settings.elasticsearch_search_timeout_seconds == 2.0
    assert settings.elasticsearch_search_max_retries == 0
    assert settings.elasticsearch_index_timeout_seconds == 30.0
    assert settings.elasticsearch_index_max_retries == 3


def test_cliente_de_indexacao_usa_timeouts_longos(monkeypatch: Any) -> None:
    captured: dict[str, object] = {}

    class _Recorder:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(es_mod, "AsyncElasticsearch", _Recorder)
    es_mod._create_client(
        Settings(elasticsearch_index_timeout_seconds=25.0, elasticsearch_index_max_retries=2)
    )
    assert captured["request_timeout"] == 25.0
    assert captured["max_retries"] == 2


def _index(client: object) -> es_mod.ElasticsearchProductIndex:
    return es_mod.ElasticsearchProductIndex(
        client=cast(Any, client),
        alias="forja_products",
        search_timeout_seconds=1.5,
        search_max_retries=0,
    )


async def test_busca_usa_timeout_curto_e_sem_retries() -> None:
    client = _FakeClient()
    await _index(client).search(_QUERY)
    assert client.options_kwargs == {
        "request_timeout": 1.5,
        "max_retries": 0,
        "retry_on_timeout": False,
    }
    assert client.search_kwargs is not None


async def test_autocomplete_usa_timeout_curto_e_sem_retries() -> None:
    client = _FakeClient()
    await _index(client).autocomplete(q="cap", limit=5)
    assert client.options_kwargs == {
        "request_timeout": 1.5,
        "max_retries": 0,
        "retry_on_timeout": False,
    }


async def _usecase(primary: _FlakyPrimary) -> SearchProducts:
    return SearchProducts(
        primary=primary,
        fallback=_Fallback(),
        semantic=None,
        product_reader=_EmptyReader(),
        settings=Settings(
            search_circuit_breaker_failures=2,
            search_circuit_breaker_cooldown_seconds=0.05,
        ),
    )


async def test_circuit_breaker_abre_e_retoma() -> None:
    primary = _FlakyPrimary(fail=True)
    use_case = await _usecase(primary)

    assert (await use_case.run(query=_QUERY, auth=None)).search_mode == "postgres_fallback"
    assert primary.calls == 1
    assert (await use_case.run(query=_QUERY, auth=None)).search_mode == "postgres_fallback"
    assert primary.calls == 2  # 2 falhas -> breaker aberto

    # Dentro do cooldown: Elasticsearch e ignorado (sem nova chamada).
    assert (await use_case.run(query=_QUERY, auth=None)).search_mode == "postgres_fallback"
    assert primary.calls == 2

    # Meia-abertura: apos o cooldown, tenta de novo; ES voltou -> fecha o breaker.
    await asyncio.sleep(0.06)
    primary.fail = False
    assert (await use_case.run(query=_QUERY, auth=None)).search_mode == "lexical"
    assert primary.calls == 3

    # Breaker fechado: volta a consultar normalmente.
    assert (await use_case.run(query=_QUERY, auth=None)).search_mode == "lexical"
    assert primary.calls == 4
