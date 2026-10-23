"""Testes unitarios do servico de idempotencia (sem banco)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.application.idempotency import (
    IdempotencyInProgressError,
    IdempotencyKeyInvalidError,
    IdempotencyPayloadMismatchError,
    IdempotencyScope,
    IdempotencyService,
    ReserveResult,
    ReserveState,
    validate_idempotency_key,
)

_SCOPE = IdempotencyScope(
    company_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
    user_id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
    method="POST",
    route="/api/v1/orders",
)
_NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self, *, reserve: ReserveResult | None = None) -> None:
        self.reserve_result = reserve or ReserveResult(state=ReserveState.RESERVED)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.completed = False
        self.released = False

    async def reserve(self, **kwargs: Any) -> ReserveResult:
        self.calls.append(("reserve", kwargs))
        return self.reserve_result

    async def complete(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        status_code: int,
        body: dict[str, Any] | None,
        expires_at: datetime,
    ) -> bool:
        self.completed = True
        return True

    async def release(self, *, scope: IdempotencyScope, key: str, request_hash: str) -> bool:
        self.released = True
        return True


def _service(repository: FakeRepository) -> IdempotencyService:
    return IdempotencyService(repository=repository, now=lambda: _NOW)


def test_chave_aceita_uuid_e_string_longa() -> None:
    assert validate_idempotency_key(str(uuid.uuid4()))
    assert validate_idempotency_key("a" * 16)
    assert validate_idempotency_key("a" * 128)


@pytest.mark.parametrize(
    "key",
    ["curta", "a" * 129, "com espaco 1234567890", "chave\ncom-quebra-123"],
)
def test_chave_invalida_422(key: str) -> None:
    with pytest.raises(IdempotencyKeyInvalidError):
        validate_idempotency_key(key)


async def test_begin_replay_devolve_resposta_original() -> None:
    repository = FakeRepository(
        reserve=ReserveResult(
            state=ReserveState.REPLAY,
            response_status=201,
            response_body={"id": "pedido-1"},
        )
    )

    result = await _service(repository).begin(scope=_SCOPE, key="a" * 16, request_hash="hash")

    assert result.replay is True
    assert result.status_code == 201
    assert result.body == {"id": "pedido-1"}


async def test_begin_payload_diferente_422() -> None:
    repository = FakeRepository(reserve=ReserveResult(state=ReserveState.MISMATCH))

    with pytest.raises(IdempotencyPayloadMismatchError):
        await _service(repository).begin(scope=_SCOPE, key="a" * 16, request_hash="hash")


async def test_begin_em_andamento_409_com_retry_after() -> None:
    repository = FakeRepository(
        reserve=ReserveResult(state=ReserveState.IN_PROGRESS, retry_after_seconds=7)
    )

    with pytest.raises(IdempotencyInProgressError) as exc_info:
        await _service(repository).begin(scope=_SCOPE, key="a" * 16, request_hash="hash")

    assert exc_info.value.status_code == 409
    assert exc_info.value.headers == {"Retry-After": "7"}


async def test_complete_e_release_delegam_ao_repositorio() -> None:
    repository = FakeRepository()
    service = _service(repository)

    assert await service.complete(
        scope=_SCOPE,
        key="a" * 16,
        request_hash="hash",
        status_code=201,
        body={"id": "x"},
    )
    assert repository.completed is True

    await service.release(scope=_SCOPE, key="a" * 16, request_hash="hash")
    assert repository.released is True


async def test_reserva_recebe_ttl_de_andamento() -> None:
    repository = FakeRepository()
    service = IdempotencyService(
        repository=repository,
        in_progress_ttl_seconds=30,
        now=lambda: _NOW,
    )

    await service.begin(scope=_SCOPE, key="a" * 16, request_hash="hash")

    assert repository.calls[0][1]["expires_at"] == _NOW + timedelta(seconds=30)
