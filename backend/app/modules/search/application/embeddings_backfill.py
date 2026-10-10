"""Backfill/reindexacao vetorial idempotente a partir do PostgreSQL (Fase 5).

Le o catalogo em lotes, calcula o texto embutido e so grava quando o
``content_hash`` mudou. Reexecutar nao duplica (upsert por ``product_id``) e
remove vetores de produtos que deixaram de ser vendaveis. Nenhum preco entra.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.core.logging import get_logger
from app.modules.search.application.documents import is_row_sellable
from app.modules.search.application.embedding_text import (
    build_embedding_text,
    compute_content_hash,
)
from app.modules.search.application.ports import (
    EmbeddingEntry,
    EmbeddingProvider,
    ProductReader,
    ProductRow,
    VectorStore,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class EmbeddingBackfillReport:
    """Relatorio de um backfill vetorial."""

    checked: int
    embedded: int
    skipped: int
    removed: int
    dry_run: bool


class BackfillEmbeddings:
    """Gera/atualiza embeddings idempotentemente (por hash) em lotes."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        store: VectorStore,
        reader: ProductReader,
        batch_size: int,
    ) -> None:
        self._provider = provider
        self._store = store
        self._reader = reader
        self._batch_size = batch_size

    async def run(self, *, dry_run: bool = False) -> EmbeddingBackfillReport:
        today = date.today()
        existing = await self._store.get_hashes()
        sellable_ids: set[uuid.UUID] = set()
        checked = 0
        embedded = 0
        skipped = 0
        pending: list[tuple[ProductRow, str]] = []
        async for batch in self._reader.iter_products(batch_size=self._batch_size):
            for row in batch:
                checked += 1
                if not is_row_sellable(row, today=today):
                    continue
                sellable_ids.add(row.id)
                text = build_embedding_text(row)
                digest = compute_content_hash(text, self._provider.model)
                if existing.get(row.id) == digest:
                    skipped += 1
                    continue
                pending.append((row, digest))
                if len(pending) >= self._batch_size:
                    embedded += await self._flush(pending, dry_run=dry_run)
                    pending = []
        embedded += await self._flush(pending, dry_run=dry_run)

        orphans = [product_id for product_id in existing if product_id not in sellable_ids]
        removed = len(orphans) if dry_run else await self._store.delete(orphans)
        _logger.info(
            "search_embeddings_backfill_done",
            checked=checked,
            embedded=embedded,
            skipped=skipped,
            removed=removed,
            dry_run=dry_run,
        )
        return EmbeddingBackfillReport(
            checked=checked,
            embedded=embedded,
            skipped=skipped,
            removed=removed,
            dry_run=dry_run,
        )

    async def _flush(self, pending: list[tuple[ProductRow, str]], *, dry_run: bool) -> int:
        if not pending or dry_run:
            return len(pending)
        texts = [build_embedding_text(row) for row, _digest in pending]
        vectors = await self._provider.embed_documents(texts)
        entries = [
            EmbeddingEntry(
                product_id=row.id,
                model=self._provider.model,
                dimension=self._provider.dimension,
                embedding=vector,
                content_hash=digest,
            )
            for (row, digest), vector in zip(pending, vectors, strict=True)
        ]
        return await self._store.upsert_many(entries)


class EmbeddingSync:
    """Atualiza/rem o vetor de um unico produto (hash-aware), por evento da outbox."""

    def __init__(self, *, provider: EmbeddingProvider, store: VectorStore) -> None:
        self._provider = provider
        self._store = store

    async def upsert_row(self, row: ProductRow) -> bool:
        """Recalcula e grava o vetor somente se o conteudo mudou."""
        text = build_embedding_text(row)
        digest = compute_content_hash(text, self._provider.model)
        if await self._store.get_hash(row.id) == digest:
            return False
        vector = (await self._provider.embed_documents([text]))[0]
        await self._store.upsert_many(
            [
                EmbeddingEntry(
                    product_id=row.id,
                    model=self._provider.model,
                    dimension=self._provider.dimension,
                    embedding=vector,
                    content_hash=digest,
                )
            ]
        )
        return True

    async def delete(self, product_id: uuid.UUID) -> None:
        await self._store.delete([product_id])
