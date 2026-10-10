"""Repositorio SQLAlchemy da outbox de busca (global, sem RLS).

Os eventos sao gravados na mesma transacao da alteracao do produto e lidos pelo
worker. Eventos falhos permanecem com status FAILED e sao reprocessaveis
enquanto ``attempts < max_attempts`` (nunca descartados silenciosamente).
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.ports import SearchOutboxEvent

_LIST_DUE = text(
    "SELECT id, aggregate_id, event_type, version, attempts FROM search_outbox "
    "WHERE status = 'PENDING' OR (status = 'FAILED' AND attempts < :max_attempts) "
    "ORDER BY created_at ASC LIMIT :limit"
)
_MARK_PROCESSED = text(
    "UPDATE search_outbox SET status = 'PROCESSED', attempts = attempts + 1, "
    "updated_at = now() WHERE id = :id"
)
_MARK_FAILED = text(
    "UPDATE search_outbox SET status = 'FAILED', attempts = attempts + 1, "
    "last_error = :error, updated_at = now() WHERE id = :id"
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

    async def mark_failed(self, event_id: uuid.UUID, *, error: str) -> None:
        async with self._uow_factory.begin() as uow:
            await uow.session.execute(_MARK_FAILED, {"id": event_id, "error": error})
            await uow.commit()
