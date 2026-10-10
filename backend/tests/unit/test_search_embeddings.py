"""Testes unitarios de embeddings (Fase 5): texto, hash, pooling, backfill e sync."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.modules.search.application.embedding_text import (
    build_embedding_text,
    compute_content_hash,
)
from app.modules.search.application.embeddings_backfill import (
    BackfillEmbeddings,
    EmbeddingSync,
)
from app.modules.search.application.ports import (
    EmbeddingEntry,
    ProductRow,
    SearchQuery,
    VectorHit,
)
from app.modules.search.infrastructure.embeddings import (
    build_embedding_provider,
    mean_pool_normalize,
)

_FAR_FUTURE = date(2099, 12, 31)


def _row(
    key: str,
    *,
    status: str = "ACTIVE",
    description: str | None = "descricao do produto",
    base_unit_price: Decimal = Decimal("999.90"),
) -> ProductRow:
    return ProductRow(
        id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        sku=key.upper(),
        name=f"Produto {key}",
        description=description,
        slug=key.lower(),
        status=status,
        is_epi=False,
        ca_number=None,
        ca_valid_until=_FAR_FUTURE,
        category_id=uuid.uuid5(uuid.NAMESPACE_URL, "cat"),
        category_name="Categoria",
        category_slug="categoria",
        brand_id=uuid.uuid5(uuid.NAMESPACE_URL, "brand"),
        brand_name="Marca",
        brand_slug="marca",
        attributes=None,
        base_unit_price=base_unit_price,
        currency="BRL",
        min_order_qty=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class _FakeProvider:
    def __init__(self, *, dimension: int = 4, fail: bool = False) -> None:
        self._dimension = dimension
        self._fail = fail
        self.calls = 0

    @property
    def model(self) -> str:
        return "fake-model"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        assert not self._fail
        self.calls += 1
        return [[float(len(text))] * self._dimension for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [float(len(text))] * self._dimension


class _FakeVectorStore:
    def __init__(self, hits: list[VectorHit] | None = None) -> None:
        self.rows: dict[uuid.UUID, str] = {}
        self.vectors: dict[uuid.UUID, list[float]] = {}
        self.deleted: list[uuid.UUID] = []
        self._hits = hits or []

    async def upsert_many(self, entries: Sequence[EmbeddingEntry]) -> int:
        for entry in entries:
            self.rows[entry.product_id] = entry.content_hash
            self.vectors[entry.product_id] = entry.embedding
        return len(entries)

    async def get_hashes(self) -> dict[uuid.UUID, str]:
        return dict(self.rows)

    async def get_hash(self, product_id: uuid.UUID) -> str | None:
        return self.rows.get(product_id)

    async def search_similar(
        self, *, embedding: Sequence[float], filters: SearchQuery, limit: int
    ) -> list[VectorHit]:
        return self._hits[:limit]

    async def delete(self, product_ids: Sequence[uuid.UUID]) -> int:
        for product_id in product_ids:
            self.rows.pop(product_id, None)
            self.vectors.pop(product_id, None)
        self.deleted.extend(product_ids)
        return len(product_ids)


class _FakeReader:
    def __init__(self, rows: list[ProductRow]) -> None:
        self._rows = rows

    def iter_products(self, *, batch_size: int) -> AsyncIterator[list[ProductRow]]:
        async def _gen() -> AsyncIterator[list[ProductRow]]:
            for start in range(0, len(self._rows), batch_size):
                yield self._rows[start : start + batch_size]

        return _gen()

    async def get_product(self, product_id: uuid.UUID) -> ProductRow | None:
        return next((row for row in self._rows if row.id == product_id), None)

    async def get_products_by_ids(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ProductRow]:
        return {row.id: row for row in self._rows if row.id in product_ids}


def test_texto_embutido_nao_contem_preco_nem_dado_privado() -> None:
    text = build_embedding_text(_row("A"))
    assert "Produto A" in text
    assert "Marca" in text and "Categoria" in text
    assert "999" not in text
    assert "preco" not in text.lower()


def test_hash_muda_com_texto_e_modelo() -> None:
    baseline = compute_content_hash("texto", "model-a")
    assert baseline == compute_content_hash("texto", "model-a")
    assert baseline != compute_content_hash("outro", "model-a")
    assert baseline != compute_content_hash("texto", "model-b")


def test_mean_pool_ignora_tokens_mascarados_e_normaliza() -> None:
    vectors = [[1.0, 0.0], [100.0, 100.0], [3.0, 0.0]]
    pooled = mean_pool_normalize(vectors, [1, 0, 1])
    assert pooled[1] == 0.0  # token mascarado nao contribui
    assert pooled[0] == pytest.approx(1.0)
    assert pooled[0] ** 2 + pooled[1] ** 2 == pytest.approx(1.0)


def test_mean_pool_vazio_retorna_vazio() -> None:
    assert mean_pool_normalize([], []) == []


async def test_backfill_idempotente_embeda_uma_vez() -> None:
    rows = [_row("A"), _row("B")]
    provider = _FakeProvider()
    store = _FakeVectorStore()
    use_case = BackfillEmbeddings(
        provider=provider, store=store, reader=_FakeReader(rows), batch_size=1
    )
    first = await use_case.run()
    assert (first.embedded, first.skipped) == (2, 0)
    assert len(store.rows) == 2
    calls_after_first = provider.calls
    second = await use_case.run()
    assert (second.embedded, second.skipped) == (0, 2)
    assert provider.calls == calls_after_first  # conteudo inalterado nao recalcula


async def test_backfill_remove_vetores_orfaos_e_nao_vendaveis() -> None:
    sellable = _row("A")
    inactive = _row("B", status="INACTIVE")
    store = _FakeVectorStore()
    store.rows[inactive.id] = "hash-antigo"
    use_case = BackfillEmbeddings(
        provider=_FakeProvider(),
        store=store,
        reader=_FakeReader([sellable, inactive]),
        batch_size=10,
    )
    report = await use_case.run()
    assert report.removed == 1
    assert inactive.id not in store.rows
    assert report.embedded == 1  # apenas o vendavel


async def test_backfill_dry_run_nao_grava() -> None:
    store = _FakeVectorStore()
    provider = _FakeProvider()
    use_case = BackfillEmbeddings(
        provider=provider, store=store, reader=_FakeReader([_row("A")]), batch_size=10
    )
    report = await use_case.run(dry_run=True)
    assert report.embedded == 1
    assert store.rows == {}
    assert provider.calls == 0


async def test_embedding_sync_e_hash_aware() -> None:
    row = _row("A")
    store = _FakeVectorStore()
    sync = EmbeddingSync(provider=_FakeProvider(), store=store)
    assert await sync.upsert_row(row) is True
    assert await sync.upsert_row(row) is False  # hash inalterado
    await sync.delete(row.id)
    assert row.id not in store.rows


def test_build_embedding_provider_desabilitado_ou_sem_modelo() -> None:
    assert build_embedding_provider(Settings(embeddings_enabled=False)) is None
    settings = Settings(embeddings_enabled=True, embedding_model_path="/nao/existe/modelo")
    assert build_embedding_provider(settings) is None
