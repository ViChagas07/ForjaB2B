"""Casos de uso de sincronizacao do indice de busca (Fase 3).

O PostgreSQL e a fonte de verdade; o indice derivado e reconstruivel a partir
dele. Nenhum caso de uso grava no PostgreSQL. Falhas de indexacao nao sao
perdidas: eventos ficam registrados na outbox para reprocessamento.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.core.logging import get_logger
from app.core.metrics import observe_outbox_snapshot
from app.modules.search.application.documents import build_product_document, is_row_sellable
from app.modules.search.application.embeddings_backfill import EmbeddingSync
from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.ports import (
    IndexBulkResult,
    ProductIndex,
    ProductReader,
    ProductRow,
    SearchEventType,
    SearchOutboxEvent,
    SearchOutboxMetricsReader,
    SearchOutboxRepository,
    SearchOutboxStats,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, kw_only=True)
class ReindexReport:
    """Relatorio de uma reindexacao completa."""

    index_name: str | None
    indexed: int
    expected: int
    rejected: int
    count: int
    orphans_removed: int
    swapped: bool
    dry_run: bool


@dataclass(frozen=True, kw_only=True)
class ReconcileReport:
    """Relatorio de uma reconciliacao Postgres x indice."""

    checked: int
    upserted: int
    deleted: int
    rejected: int


@dataclass(frozen=True, kw_only=True)
class ReconcileRun:
    """Resultado de uma tentativa de reconciliacao (inclusive bloqueada)."""

    status: str
    report: ReconcileReport | None
    duration: float


@dataclass(frozen=True, kw_only=True)
class DispatchReport:
    """Relatorio do processamento da outbox de busca."""

    candidates: int
    processed: int
    failed: int
    dead: int = 0


class ReindexProducts:
    """Reconstroi o indice versionado a partir do PostgreSQL (repetivel)."""

    def __init__(
        self,
        *,
        index: ProductIndex,
        reader: ProductReader,
        replicas: int,
        count_tolerance: int = 0,
    ) -> None:
        self._index = index
        self._reader = reader
        self._replicas = replicas
        self._count_tolerance = count_tolerance

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
                rejected=0,
                count=0,
                orphans_removed=0,
                swapped=False,
                dry_run=True,
            )

        index_name = await self._index.create_versioned_index(
            version=version, replicas=self._replicas
        )
        expected, indexed, rejected, expected_ids = await self._index_all(
            index_name=index_name, batch_size=batch_size, today=today
        )
        await self._index.refresh(target=index_name)

        if rejected:
            _logger.warning("search_reindex_rejected", index=index_name, rejected=rejected)
            raise SearchIndexError(
                f"{rejected} documento(s) rejeitado(s) pelo Elasticsearch em {index_name}; "
                "alias NAO trocado (o indice anterior continua servindo)"
            )

        existing = await self._index.fetch_versions(target=index_name)
        orphans = [doc_id for doc_id in existing if doc_id not in expected_ids]
        if orphans:
            await self._index.delete_documents(target=index_name, ids=orphans)
            await self._index.refresh(target=index_name)

        count = await self._index.count(target=index_name)
        if abs(count - expected) > self._count_tolerance:
            _logger.warning(
                "search_reindex_count_mismatch",
                index=index_name,
                count=count,
                expected=expected,
                tolerance=self._count_tolerance,
            )
            raise SearchIndexError(
                f"contagem divergente no indice {index_name}: {count} != {expected} "
                f"(tolerancia {self._count_tolerance}); alias NAO trocado"
            )

        await self._index.swap_alias(index_name=index_name)
        _logger.info(
            "search_reindex_done",
            index=index_name,
            indexed=indexed,
            expected=expected,
            count=count,
            orphans_removed=len(orphans),
        )
        return ReindexReport(
            index_name=index_name,
            indexed=indexed,
            expected=expected,
            rejected=0,
            count=count,
            orphans_removed=len(orphans),
            swapped=True,
            dry_run=False,
        )

    async def _index_all(
        self, *, index_name: str, batch_size: int, today: date
    ) -> tuple[int, int, int, set[str]]:
        """Indexa todos os produtos vendaveis; devolve (expected, indexed, rejected, ids)."""
        expected = 0
        indexed = 0
        rejected = 0
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
                rejected += result.errors
                if result.errors:
                    _logger.warning(
                        "search_reindex_batch_rejected",
                        index=index_name,
                        rejected=result.errors,
                        reasons=list(result.sample_errors),
                    )
        return expected, indexed, rejected, expected_ids


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
        deleted = 0
        rejected = 0
        if to_upsert:
            documents = [build_product_document(row, today=today) for row in to_upsert]
            result = await self._index.index_documents(
                target=self._index.alias, documents=documents
            )
            upserted = result.indexed
            rejected += result.errors
            if result.errors:
                _logger.warning(
                    "search_reconcile_rejected",
                    operation="upsert",
                    rejected=result.errors,
                    reasons=list(result.sample_errors),
                )
            await self._index.refresh(target=self._index.alias)

        if to_delete:
            result = await self._index.delete_documents(target=self._index.alias, ids=to_delete)
            deleted = result.deleted
            rejected += result.errors
            if result.errors:
                _logger.warning(
                    "search_reconcile_rejected",
                    operation="delete",
                    rejected=result.errors,
                    reasons=list(result.sample_errors),
                )
            await self._index.refresh(target=self._index.alias)

        _logger.info(
            "search_reconcile_done",
            checked=len(versions),
            upserted=upserted,
            deleted=deleted,
            rejected=rejected,
        )
        return ReconcileReport(
            checked=len(versions), upserted=upserted, deleted=deleted, rejected=rejected
        )


class DispatchSearchOutbox:
    """Aplica os eventos pendentes da outbox no indice (com retry/registro)."""

    def __init__(
        self,
        *,
        index: ProductIndex,
        reader: ProductReader,
        outbox: SearchOutboxRepository,
        max_attempts: int,
        embedding_sync: EmbeddingSync | None = None,
    ) -> None:
        self._index = index
        self._reader = reader
        self._outbox = outbox
        self._max_attempts = max_attempts
        self._embedding_sync = embedding_sync

    async def run(self, *, limit: int = 100) -> DispatchReport:
        events = await self._outbox.list_due(limit=limit, max_attempts=self._max_attempts)
        today = date.today()
        processed = 0
        failed = 0
        dead = 0
        for event in events:
            try:
                await self._apply(event, today=today)
            except Exception as exc:  # noqa: BLE001 - falha registrada, nunca perdida
                failed += 1
                is_dead = event.attempts + 1 >= self._max_attempts
                if is_dead:
                    dead += 1
                # Somente o tipo da excecao: motivo resumido e sem dados
                # sensiveis (nem IDs de produto, nem URLs/credenciais).
                await self._outbox.mark_failed(event.id, error=type(exc).__name__, dead=is_dead)
                _logger.warning(
                    "search_outbox_event_failed",
                    event_id=str(event.id),
                    error=type(exc).__name__,
                    attempts=event.attempts + 1,
                    dead=is_dead,
                )
            else:
                processed += 1
                await self._outbox.mark_processed(event.id)
        if events:
            try:
                await self._index.refresh(target=self._index.alias)
            except Exception as exc:  # noqa: BLE001 - refresh nao desfaz o processamento
                # O estado de cada evento ja foi persistido. Se o ES caiu depois,
                # o proximo ciclo/reconcile torna as escritas visiveis.
                _logger.warning("search_outbox_refresh_failed", error=type(exc).__name__)
        return DispatchReport(candidates=len(events), processed=processed, failed=failed, dead=dead)

    async def _apply(self, event: SearchOutboxEvent, *, today: date) -> None:
        product_id = str(event.aggregate_id)
        if event.event_type == SearchEventType.DELETE.value:
            result = await self._index.delete_documents(target=self._index.alias, ids=[product_id])
            self._require_accepted(result)
            await self._delete_embedding(event.aggregate_id)
            return
        row = await self._reader.get_product(event.aggregate_id)
        if row is None or not is_row_sellable(row, today=today):
            result = await self._index.delete_documents(target=self._index.alias, ids=[product_id])
            self._require_accepted(result)
            await self._delete_embedding(event.aggregate_id)
            return
        document = build_product_document(row, today=today)
        result = await self._index.index_documents(target=self._index.alias, documents=[document])
        self._require_accepted(result)
        await self._upsert_embedding(row)

    @staticmethod
    def _require_accepted(result: IndexBulkResult) -> None:
        """Documento rejeitado pelo ES vira falha do evento (reprocessavel)."""
        if result.errors:
            raise SearchIndexError(
                f"{result.errors} documento(s) rejeitado(s) pelo Elasticsearch "
                f"({', '.join(result.sample_errors)}); evento sera reprocessado"
            )

    async def _delete_embedding(self, product_id: uuid.UUID) -> None:
        if self._embedding_sync is None:
            return
        try:
            await self._embedding_sync.delete(product_id)
        except Exception:  # noqa: BLE001 - embedding nunca bloqueia a busca lexical
            _logger.warning("search_embedding_sync_failed", product_id=str(product_id))

    async def _upsert_embedding(self, row: ProductRow) -> None:
        if self._embedding_sync is None:
            return
        try:
            await self._embedding_sync.upsert_row(row)
        except Exception:  # noqa: BLE001 - embedding nunca bloqueia a busca lexical
            _logger.warning("search_embedding_sync_failed", product_id=str(row.id))


class RefreshSearchMetrics:
    """Atualiza os gauges da outbox a partir do estado persistido.

    Roda no processo da API (nao no worker) para que o Prometheus, que faz
    scrape do backend, veja os valores reais independentemente de quem
    processou os eventos.
    """

    def __init__(self, *, outbox: SearchOutboxMetricsReader) -> None:
        self._outbox = outbox

    async def run(self) -> SearchOutboxStats:
        stats = await self._outbox.stats()
        observe_outbox_snapshot(
            pending=stats.pending,
            dead=stats.dead,
            oldest_pending_age_seconds=stats.oldest_pending_age_seconds,
        )
        return stats
