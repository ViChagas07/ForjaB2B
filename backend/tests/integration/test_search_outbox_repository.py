"""Integracao da outbox de busca com PostgreSQL real (dead-letter, backoff, requeue)."""

from __future__ import annotations

import uuid

import psycopg

from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.infrastructure.outbox_repository import (
    SqlAlchemySearchOutboxRepository,
)

_INSERT = (
    "INSERT INTO search_outbox "
    "(id, aggregate_id, event_type, version, status, attempts, last_error, created_at, updated_at) "
    "VALUES (%s, %s, 'UPSERT', 1, %s, %s, NULL, now() - interval '1 hour', now())"
)


def _insert(
    conn: psycopg.Connection,
    *,
    event_id: uuid.UUID,
    aggregate_id: uuid.UUID,
    status: str,
    attempts: int,
) -> None:
    conn.execute(_INSERT, (event_id, aggregate_id, status, attempts))


async def test_backoff_dead_letter_e_requeue(
    admin_conn: psycopg.Connection,
    uow_factory: SqlAlchemyUnitOfWorkFactory,
    migrated_domain_schema: None,
) -> None:
    repository = SqlAlchemySearchOutboxRepository(uow_factory)
    event_id = uuid.uuid4()
    aggregate_id = uuid.uuid4()
    _insert(admin_conn, event_id=event_id, aggregate_id=aggregate_id, status="FAILED", attempts=1)
    try:
        # attempts=1 com updated_at=now(): ainda dentro do backoff (2 s), nao aparece.
        due = await repository.list_due(limit=100, max_attempts=5)
        assert event_id not in {event.id for event in due}

        # Simula que o backoff passou.
        admin_conn.execute(
            "UPDATE search_outbox SET updated_at = now() - interval '3 seconds' WHERE id = %s",
            (event_id,),
        )
        due = await repository.list_due(limit=100, max_attempts=5)
        assert event_id in {event.id for event in due}

        # attempts=1 + nova falha = 2 < 5: continua retentavel.
        await repository.mark_failed(event_id, error="ConnectionTimeout", dead=False)
        status = admin_conn.execute(
            "SELECT status, attempts FROM search_outbox WHERE id = %s", (event_id,)
        ).fetchone()
        assert status == ("FAILED", 2)

        # Forca a ultima tentativa e marca dead-letter.
        admin_conn.execute(
            "UPDATE search_outbox SET attempts = 4, updated_at = now() - interval '1 minute' "
            "WHERE id = %s",
            (event_id,),
        )
        await repository.mark_failed(event_id, error="ConnectionTimeout", dead=True)
        row = admin_conn.execute(
            "SELECT status, attempts, last_error FROM search_outbox WHERE id = %s", (event_id,)
        ).fetchone()
        assert row == ("DEAD_LETTERED", 5, "ConnectionTimeout")

        dead = await repository.list_dead(limit=100)
        assert event_id in {event.id for event in dead}
        stats = await repository.stats()
        assert stats.dead >= 1
        assert stats.oldest_pending_age_seconds >= 0

        # Requeue devolve a PENDING, zera tentativas e o motivo.
        assert await repository.requeue(event_id) is True
        requeued = admin_conn.execute(
            "SELECT status, attempts, last_error FROM search_outbox WHERE id = %s", (event_id,)
        ).fetchone()
        assert requeued == ("PENDING", 0, None)
        assert event_id not in {event.id for event in await repository.list_dead(limit=100)}

        # Um segundo requeue do mesmo id nao encontra mais nada (idempotente).
        assert await repository.requeue(event_id) is False
    finally:
        admin_conn.execute("DELETE FROM search_outbox WHERE id = %s", (event_id,))
