"""Testes unitarios da busca hibrida e dos modos de degradacao (Fase 5)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.domain.pricing import CompanyPriceRule
from app.modules.search.application.errors import SearchUnavailableError
from app.modules.search.application.ports import (
    EmbeddingEntry,
    ProductReader,
    ProductRow,
    SearchQuery,
    SearchReader,
    SearchResult,
    SearchSuggestion,
    VectorHit,
)
from app.modules.search.application.search import SearchProducts
from app.modules.search.application.semantic import SemanticSearch

_FAR_FUTURE = date(2099, 12, 31)


def _row(key: str) -> ProductRow:
    return ProductRow(
        id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        sku=key.upper(),
        name=f"Produto {key}",
        description=None,
        slug=key.lower(),
        status="ACTIVE",
        is_epi=False,
        ca_number=None,
        ca_valid_until=_FAR_FUTURE,
        category_id=uuid.uuid5(uuid.NAMESPACE_URL, "cat"),
        category_name="Categoria",
        category_slug="categoria",
        brand_id=None,
        brand_name=None,
        brand_slug=None,
        attributes=None,
        image_url=None,
        base_unit_price=Decimal("10.00"),
        currency="BRL",
        min_order_qty=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class _FakeLexical(SearchReader):
    def __init__(self, ids: list[str], *, mode: str = "lexical", fail: bool = False) -> None:
        self._ids = ids
        self._mode = mode
        self._fail = fail
        self.calls = 0

    async def search(self, query: SearchQuery) -> SearchResult:
        self.calls += 1
        if self._fail:
            raise SearchUnavailableError("down")
        return SearchResult(ids=list(self._ids), total=len(self._ids), mode=self._mode)

    async def autocomplete(self, *, q: str, limit: int) -> list[SearchSuggestion]:
        return []


class _FakeProductReader(ProductReader):
    def __init__(self, rows: list[ProductRow]) -> None:
        self._rows = {row.id: row for row in rows}

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
        return {}

    async def get_category_name_map(self, locale: str) -> dict[str, str]:
        return {}


class _FakeProvider:
    @property
    def model(self) -> str:
        return "fake"

    @property
    def dimension(self) -> int:
        return 3

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class _SlowProvider(_FakeProvider):
    async def embed_query(self, text: str) -> list[float]:
        await asyncio.sleep(0.2)
        return [1.0, 0.0, 0.0]


class _FakeVectorStore:
    def __init__(self, hits: list[VectorHit], *, fail: bool = False) -> None:
        self._hits = hits
        self._fail = fail

    async def upsert_many(self, entries: Sequence[EmbeddingEntry]) -> int:
        return len(entries)

    async def get_hashes(self) -> dict[uuid.UUID, str]:
        return {}

    async def get_hash(self, product_id: uuid.UUID) -> str | None:
        return None

    async def search_similar(
        self, *, embedding: Sequence[float], filters: SearchQuery, limit: int
    ) -> list[VectorHit]:
        if self._fail:
            raise SearchUnavailableError("pgvector down")
        return self._hits[:limit]

    async def delete(self, product_ids: Sequence[uuid.UUID]) -> int:
        return len(product_ids)


def _settings() -> Settings:
    return Settings(
        search_max_query_length=100,
        search_max_page_size=100,
        search_max_deep_pagination=5000,
        embedding_candidate_limit=10,
        embedding_query_timeout_seconds=1.0,
        embedding_rrf_k=60,
    )


def _query(q: str | None) -> SearchQuery:
    return SearchQuery(q=q, category_id=None, brand_id=None, is_epi=None, page=1, page_size=20)


def _usecase(
    *,
    lexical: SearchReader,
    fallback: SearchReader,
    semantic: SemanticSearch | None,
    rows: list[ProductRow],
) -> SearchProducts:
    return SearchProducts(
        primary=lexical,
        fallback=fallback,
        semantic=semantic,
        product_reader=_FakeProductReader(rows),
        settings=_settings(),
    )


async def test_hibrido_quando_os_dois_caminhos_respondem() -> None:
    a, b, c = _row("A"), _row("B"), _row("C")
    lexical = _FakeLexical([str(a.id), str(b.id)])
    store = _FakeVectorStore(
        [VectorHit(product_id=c.id, score=0.9), VectorHit(product_id=a.id, score=0.8)]
    )
    semantic = SemanticSearch(
        provider=_FakeProvider(), store=store, candidate_limit=10, timeout_seconds=1.0
    )
    result = await _usecase(
        lexical=lexical, fallback=_FakeLexical([]), semantic=semantic, rows=[a, b, c]
    ).run(query=_query("luva de seguranca"), auth=None)
    assert result.search_mode == "hybrid"
    assert result.items[0].id == a.id  # presente nas duas listas (RRF)


async def test_degradacao_para_lexical_quando_vetorial_indisponivel() -> None:
    a = _row("A")
    lexical = _FakeLexical([str(a.id)])
    store = _FakeVectorStore([], fail=True)
    semantic = SemanticSearch(
        provider=_FakeProvider(), store=store, candidate_limit=10, timeout_seconds=1.0
    )
    result = await _usecase(
        lexical=lexical, fallback=_FakeLexical([]), semantic=semantic, rows=[a]
    ).run(query=_query("luva"), auth=None)
    assert result.search_mode == "lexical"


async def test_degradacao_para_semantic_postgres_sem_lexical() -> None:
    a = _row("A")
    lexical = _FakeLexical([], fail=True)
    store = _FakeVectorStore([VectorHit(product_id=a.id, score=0.7)])
    semantic = SemanticSearch(
        provider=_FakeProvider(), store=store, candidate_limit=10, timeout_seconds=1.0
    )
    result = await _usecase(
        lexical=lexical, fallback=_FakeLexical([]), semantic=semantic, rows=[a]
    ).run(query=_query("luva"), auth=None)
    assert result.search_mode == "semantic_postgres"


async def test_degradacao_para_fallback_postgres_com_tudo_fora() -> None:
    a = _row("A")
    lexical = _FakeLexical([], fail=True)
    store = _FakeVectorStore([], fail=True)
    semantic = SemanticSearch(
        provider=_FakeProvider(), store=store, candidate_limit=10, timeout_seconds=1.0
    )
    fallback = _FakeLexical([str(a.id)], mode="postgres_fallback")
    result = await _usecase(lexical=lexical, fallback=fallback, semantic=semantic, rows=[a]).run(
        query=_query("luva"), auth=None
    )
    assert result.search_mode == "postgres_fallback"


async def test_erro_quando_todos_os_caminhos_falham() -> None:
    lexical = _FakeLexical([], fail=True)
    store = _FakeVectorStore([], fail=True)
    semantic = SemanticSearch(
        provider=_FakeProvider(), store=store, candidate_limit=10, timeout_seconds=1.0
    )
    fallback = _FakeLexical([], mode="postgres_fallback", fail=True)
    with pytest.raises(SearchUnavailableError):
        await _usecase(lexical=lexical, fallback=fallback, semantic=semantic, rows=[]).run(
            query=_query("luva"), auth=None
        )


async def test_timeout_do_embedding_degrada_para_lexical() -> None:
    a = _row("A")
    lexical = _FakeLexical([str(a.id)])
    store = _FakeVectorStore([VectorHit(product_id=a.id, score=0.9)])
    semantic = SemanticSearch(
        provider=_SlowProvider(), store=store, candidate_limit=10, timeout_seconds=0.01
    )
    result = await _usecase(
        lexical=lexical, fallback=_FakeLexical([]), semantic=semantic, rows=[a]
    ).run(query=_query("luva"), auth=None)
    assert result.search_mode == "lexical"


async def test_consulta_parecida_com_sku_dispensa_o_vetorial() -> None:
    a = _row("A")
    lexical = _FakeLexical([str(a.id)])
    provider = _FakeProvider()
    store = _FakeVectorStore([VectorHit(product_id=a.id, score=0.9)])
    semantic = SemanticSearch(
        provider=provider, store=store, candidate_limit=10, timeout_seconds=1.0
    )
    result = await _usecase(
        lexical=lexical, fallback=_FakeLexical([]), semantic=semantic, rows=[a]
    ).run(query=_query("CAP-001"), auth=None)
    assert result.search_mode == "lexical"
    assert lexical.calls == 1
