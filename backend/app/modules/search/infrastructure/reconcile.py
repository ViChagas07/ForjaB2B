"""Execucao da reconciliacao com exclusao mutua e metricas.

Reutilizado pelo CLI, pelo worker Celery e pelo agendador opcional da API. O
advisory lock do PostgreSQL garante que duas instancias nao reconciliem ao mesmo
tempo; a segunda recebe ``status="skipped"`` sem tocar no indice.
"""

from __future__ import annotations

import time

from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.metrics import observe_reconcile_failure, observe_reconcile_success
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.sync import (
    ReconcileRun,
    ReconcileSearchIndex,
)
from app.modules.search.infrastructure.elasticsearch import build_product_index
from app.modules.search.infrastructure.lock import PostgresAdvisoryLock
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader


class ReconcileService:
    """Roda a reconciliacao uma vez, respeitando o lock e registrando metricas."""

    def __init__(
        self,
        *,
        settings: Settings,
        engine: AsyncEngine,
        uow_factory: SqlAlchemyUnitOfWorkFactory,
    ) -> None:
        self._settings = settings
        self._engine = engine
        self._uow_factory = uow_factory

    async def run(self) -> ReconcileRun:
        index = build_product_index(self._settings)
        if index is None:
            return ReconcileRun(status="disabled", report=None, duration=0.0)
        lock = PostgresAdvisoryLock(self._engine)
        if not await lock.try_acquire():
            await index.close()
            return ReconcileRun(status="skipped", report=None, duration=0.0)
        started = time.monotonic()
        try:
            report = await ReconcileSearchIndex(
                index=index,
                reader=SqlAlchemyProductReader(self._uow_factory),
                batch_size=self._settings.elasticsearch_bulk_batch_size,
            ).run()
            duration = time.monotonic() - started
            observe_reconcile_success(
                duration=duration, upserted=report.upserted, deleted=report.deleted
            )
            return ReconcileRun(status="ok", report=report, duration=duration)
        except Exception:
            observe_reconcile_failure(duration=time.monotonic() - started)
            raise
        finally:
            await index.close()
            await lock.release()
