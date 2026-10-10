"""Casos de uso de sincronizacao do indice de busca (Fase 3).

O PostgreSQL e a fonte de verdade; o indice derivado e reconstruivel a partir
dele. Nenhum caso de uso grava no PostgreSQL. Falhas de indexacao nao sao
perdidas: eventos ficam registrados na outbox para reprocessamento.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.logging import get_logger
from app.modules.search.application.documents import build_product_document, is_row_sellable
from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.ports import (
    ProductIndex,
    ProductReader,
    ProductRow,
    SearchEventType,
    SearchOutboxEvent,
    SearchOutboxRepository,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class ReindexReport:
    """Relatorio de uma reindexacao completa."""

    index_name: str | None
    indexed: int
    expected: int
    orphans_removed: int
    swapped: bool
    dry_run: bool


@dataclass(frozen=True, kw_only=True)
class ReconcileReport:
    """Relatorio de uma reconciliacao Postgres x indice."""

    checked: int
    upserted: int
    deleted: int


@dataclass(frozen=True, kw_only=True)
class DispatchReport:
    """Relatorio do processamento da outbox de busca."""

    candidates: int
    processed: int
    failed: int


class ReindexProducts:
    """Reconstroi o indice versionado a partir do PostgreSQL (repetivel)."""

    def __init__(self, *, index: ProductIndex, reader: ProductReader, replicas: int) -> None:
        self._index = index
        self._reader = reader
        self._replicas = replicas

    async def run(self, *, version: int, batch_size: int, dry_run: bool = False) -> ReindexReport:
        today = date.today()
        if dry_run:
            expected = 0
            async for batch in self._reader.iter_products(batch_size=batch_size):
                expected += sum(1 for row in batch if is_row_sellable(row, today=today))
            _logger.info("search_reindex_dry_run", expected=expected)
            return ReindexReport(
                index_name=None,
                indexed=0,
                expected=expected,
                orphans_removed=0,
                swapped=False,
                dry_run=True,
            )

        index_name = await self._index.create_versioned_index(
            version=version, replicas=self._replicas
        )
        expected = 0
        indexed = 0
        expected_ids: set[str] = set()
        async for batch in self._reader.iter_products(batch_size=batch_size):
            documents = [
                build_product_document(row, today=today)
                for row in batch
                if is_row_sellable(row, today=today)
            ]
            expected += len(documents)
            expected_ids.update(document.id for document in documents)
            if documents:
                result = await self._index.index_documents(target=index_name, documents=documents)
                indexed += result.indexed
        await self._index.refresh(target=index_name)

        existing = await self._index.fetch_versions(target=index_name)
        orphans = [doc_id for doc_id in existing if doc_id not in expected_ids]
        if orphans:
            await self._index.delete_documents(target=index_name, ids=orphans)
            await self._index.refresh(target=index_name)

        count = await self._index.count(target=index_name)
        if count != expected:
            raise SearchIndexError(
                f"contagem divergente no indice {index_name}: {count} != {expected}"
            )

        await self._index.swap_alias(index_name=index_name)
        _logger.info(
            "search_reindex_done",
            index=index_name,
            indexed=indexed,
            expected=expected,
            orphans_removed=len(orphans),
        )
        return ReindexReport(
            index_name=index_name,
            indexed=indexed,
            expected=expected,
            orphans_removed=len(orphans),
            swapped=True,
            dry_run=False,
        )


class ReconcileSearchIndex:
    """Corrige divergencias Postgres x indice (eventos perdidos, orfaos, versoes)."""

    def __init__(self, *, index: ProductIndex, reader: ProductReader, batch_size: int) -> None:
        self._index = index
        self._reader = reader
        self._batch_size = batch_size

    async def run(self) -> ReconcileReport:
        today = date.today()
        sellable_ids: set[str] = set()
        versions: dict[str, int] = {}
        rows: dict[str, ProductRow] = {}
        async for batch in self._reader.iter_products(batch_size=self._batch_size):
            for row in batch:
                key = str(row.id)
                versions[key] = row.version
                rows[key] = row
                if is_row_sellable(row, today=today):
                    sellable_ids.add(key)

        index_versions = await self._index.fetch_versions(target=self._index.alias)
        to_upsert = [
            row
            for key, row in rows.items()
            if key in sellable_ids and index_versions.get(key, -1) < versions[key]
        ]
        to_delete = [doc_id for doc_id in index_versions if doc_id not in sellable_ids]

        upserted = 0
        if to_upsert:
            documents = [build_product_document(row, today=today) for row in to_upsert]
            result = await self._index.index_documents(
                target=self._index.alias, documents=documents
            )
            upserted = result.indexed
            await self._index.refresh(target=self._index.alias)

        deleted = 0
        if to_delete:
            result = await self._index.delete_documents(target=self._index.alias, ids=to_delete)
            deleted = result.deleted
            await self._index.refresh(target=self._index.alias)

        _logger.info(
            "search_reconcile_done",
            checked=len(versions),
            upserted=upserted,
            deleted=deleted,
        )
        return ReconcileReport(checked=len(versions), upserted=upserted, deleted=deleted)


class DispatchSearchOutbox:
    """Aplica os eventos pendentes da outbox no indice (com retry/registro)."""

    def __init__(
        self,
        *,
        index: ProductIndex,
        reader: ProductReader,
        outbox: SearchOutboxRepository,
        max_attempts: int,
    ) -> None:
        self._index = index
        self._reader = reader
        self._outbox = outbox
        self._max_attempts = max_attempts

    async def run(self, *, limit: int = 100) -> DispatchReport:
        events = await self._outbox.list_due(limit=limit, max_attempts=self._max_attempts)
        today = date.today()
        processed = 0
        failed = 0
        for event in events:
            try:
                await self._apply(event, today=today)
            except Exception as exc:  # noqa: BLE001 - falha registrada, nunca perdida
                failed += 1
                await self._outbox.mark_failed(event.id, error=type(exc).__name__)
                _logger.warning(
                    "search_outbox_event_failed",
                    event_id=str(event.id),
                    error=type(exc).__name__,
                )
            else:
                processed += 1
                await self._outbox.mark_processed(event.id)
        if events:
            await self._index.refresh(target=self._index.alias)
        return DispatchReport(candidates=len(events), processed=processed, failed=failed)

    async def _apply(self, event: SearchOutboxEvent, *, today: date) -> None:
        product_id = str(event.aggregate_id)
        if event.event_type == SearchEventType.DELETE.value:
            await self._index.delete_documents(target=self._index.alias, ids=[product_id])
            return
        row = await self._reader.get_product(event.aggregate_id)
        if row is None or not is_row_sellable(row, today=today):
            await self._index.delete_documents(target=self._index.alias, ids=[product_id])
            return
        document = build_product_document(row, today=today)
        await self._index.index_documents(target=self._index.alias, documents=[document])
