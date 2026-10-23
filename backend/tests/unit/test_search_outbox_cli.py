"""Testes do CLI administrativo da outbox (sem banco)."""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from app.modules.search.interface.cli import _outbox_command


class _FakeRepository:
    def __init__(self) -> None:
        self.dead: list[Any] = []
        self.requeued: list[uuid.UUID] = []
        self.requeue_all_calls = 0

    async def list_dead(self, *, limit: int) -> list[Any]:
        return self.dead[:limit]

    async def requeue(self, event_id: uuid.UUID) -> bool:
        self.requeued.append(event_id)
        return event_id in {event.id for event in self.dead}

    async def requeue_all(self) -> int:
        self.requeue_all_calls += 1
        return len(self.dead)


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "outbox_command": "list-dead",
        "limit": 10,
        "all": False,
        "yes": False,
        "event_id": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _dead_event() -> Any:
    from app.modules.search.application.ports import DeadOutboxEvent

    now = datetime.now(UTC)
    return DeadOutboxEvent(
        id=uuid.uuid4(),
        aggregate_id=uuid.uuid4(),
        event_type="UPSERT",
        version=1,
        attempts=5,
        last_error="ConnectionTimeout",
        created_at=now,
        updated_at=now,
    )


async def test_list_dead_serializa_eventos() -> None:
    repository = _FakeRepository()
    repository.dead = [_dead_event(), _dead_event()]
    payload = await _outbox_command(cast(Any, repository), _args())
    assert payload["count"] == 2
    events = cast(list[dict[str, object]], payload["events"])
    assert len(events) == 2
    assert events[0]["last_error"] == "ConnectionTimeout"


async def test_requeue_all_exige_confirmacao() -> None:
    repository = _FakeRepository()
    payload = await _outbox_command(
        cast(Any, repository), _args(outbox_command="requeue", all=True)
    )
    assert payload["error"] == "confirmation_required"
    assert repository.requeue_all_calls == 0


async def test_requeue_all_com_yes() -> None:
    repository = _FakeRepository()
    repository.dead = [_dead_event()]
    payload = await _outbox_command(
        cast(Any, repository), _args(outbox_command="requeue", all=True, yes=True)
    )
    assert payload == {"status": "ok", "scope": "all", "requeued": 1}
    assert repository.requeue_all_calls == 1


async def test_requeue_um_evento() -> None:
    repository = _FakeRepository()
    event = _dead_event()
    repository.dead = [event]
    payload = await _outbox_command(
        cast(Any, repository), _args(outbox_command="requeue", event_id=str(event.id))
    )
    assert payload["status"] == "ok"
    assert payload["requeued"] == 1
    assert repository.requeued == [event.id]


async def test_requeue_id_invalido_nao_toca_no_banco() -> None:
    repository = _FakeRepository()
    payload = await _outbox_command(
        cast(Any, repository), _args(outbox_command="requeue", event_id="nao-e-uuid")
    )
    assert payload["error"] == "invalid_event_id"
    assert repository.requeued == []
