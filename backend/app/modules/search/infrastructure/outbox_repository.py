"""Repositorio SQLAlchemy da outbox de busca (global, sem RLS).

Os eventos sao gravados na mesma transacao da alteracao do produto e lidos pelo
worker. Um evento falho acumula tentativas com backoff exponencial (2, 4, 8...
segundos, limitado a 60 s) e, ao atingir ``max_attempts``, passa a
``DEAD_LETTERED``. Eventos mortos podem ser listados e devolvidos a fila pelo
CLI administrativo; nada e descartado silenciosamente.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.ports import (
    DeadOutboxEvent,
    SearchOutboxEvent,
    SearchOutboxStats,
)

_LIST_DUE = text(
    "SELECT id, aggregate_id, event_type, version, attempts FROM search_outbox "
    "WHERE status = 'PENDING' OR ("
    "status = 'FAILED' AND attempts < :max_attempts "
    "AND updated_at + make_interval(secs => LEAST(power(2, attempts), 60)) <= now()"
    ") ORDER BY created_at ASC LIMIT :limit"
)
_MARK_PROCESSED = text(
    "UPDATE search_outbox SET status = 'PROCESSED', attempts = attempts + 1, "
    "updated_at = now() WHERE id = :id"
)
_MARK_FAILED = text(
    "UPDATE search_outbox SET status = :status, attempts = attempts + 1, "
    "last_error = :error, updated_at = now() WHERE id = :id"
)
_LIST_DEAD = text(
    "SELECT id, aggregate_id, event_type, version, attempts, last_error, "
    "created_at, updated_at FROM search_outbox "
    "WHERE status = 'DEAD_LETTERED' ORDER BY created_at ASC LIMIT :limit"
)
_REQUEUE_ONE = text(
    "UPDATE search_outbox SET status = 'PENDING', attempts = 0, last_error = NULL, "
    "updated_at = now() WHERE id = :id AND status = 'DEAD_LETTERED' RETURNING id"
)
_REQUEUE_ALL = text(
    "UPDATE search_outbox SET status = 'PENDING', attempts = 0, last_error = NULL, "
    "updated_at = now() WHERE status = 'DEAD_LETTERED' RETURNING id"
)
_STATS = text(
    "SELECT "
    "count(*) FILTER (WHERE status IN ('PENDING', 'FAILED')) AS pending, "
    "count(*) FILTER (WHERE status = 'DEAD_LETTERED') AS dead, "
    "coalesce(extract(epoch FROM (now() - min(created_at) "
    "FILTER (WHERE status IN ('PENDING', 'FAILED')))), 0) AS oldest_age "
    "FROM search_outbox"
)


class SqlAlchemySearchOutboxRepository:
    """Implementacao da porta SearchOutboxRepository sobre ORM + UoW."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list_due(self, *, limit: int, max_attempts: int) -> list[SearchOutboxEvent]:
        async with self._uow_factory.begin() as uow:
            rows = (
                await uow.session.execute(_LIST_DUE, {"limit": limit, "max_attempts": max_attempts})
            ).all()
            await uow.commit()
        return [
            SearchOutboxEvent(
                id=row[0],
                aggregate_id=row[1],
                event_type=row[2],
                version=int(row[3]),
                attempts=int(row[4]),
            )
            for row in rows
        ]

    async def mark_processed(self, event_id: uuid.UUID) -> None:
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(_MARK_PROCESSED, {"id": event_id})
            await uow.commit()

    async def mark_failed(self, event_id: uuid.UUID, *, error: str, dead: bool) -> None:
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(
                _MARK_FAILED,
                {"id": event_id, "error": error, "status": "DEAD_LETTERED" if dead else "FAILED"},
            )
            await uow.commit()

    async def list_dead(self, *, limit: int) -> list[DeadOutboxEvent]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_LIST_DEAD, {"limit": limit})).all()
            await uow.commit()
        return [
            DeadOutboxEvent(
                id=row[0],
                aggregate_id=row[1],
                event_type=row[2],
                version=int(row[3]),
                attempts=int(row[4]),
                last_error=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]

    async def requeue(self, event_id: uuid.UUID) -> bool:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_REQUEUE_ONE, {"id": event_id})).all()
            await uow.commit()
        return bool(rows)

    async def requeue_all(self) -> int:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_REQUEUE_ALL)).all()
            await uow.commit()
        return len(rows)

    async def stats(self) -> SearchOutboxStats:
        async with self._uow_factory.begin() as uow:
            row = (await uow.session.execute(_STATS)).one()
            await uow.commit()
        return SearchOutboxStats(
            pending=int(row[0]),
            dead=int(row[1]),
            oldest_pending_age_seconds=max(0.0, float(row[2])),
        )
