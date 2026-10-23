"""Idempotencia de mutacoes criticas (header ``Idempotency-Key``).

O servico coordena um repositorio transacional com tres estados:

- ``proceed``: a chave foi reservada (``in_progress``) e o caso de uso deve
  executar;
- ``replay``: a chave ja foi concluida com o MESMO payload; a resposta original
  e devolvida com ``Idempotent-Replayed: true``;
- ``mismatch``/``in_progress``: erros 422/409.

Falhas 5xx liberam a reserva (o chamador deve chamar ``release``), de modo que
uma nova tentativa possa criar o recurso. A resposta definitiva so e gravada
depois do sucesso do caso de uso.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.metrics import increment_idempotency_request

_logger = get_logger(__name__)

IDEMPOTENCY_HEADER = "Idempotency-Key"
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~:/+=@-]{16,128}$")
DEFAULT_TTL_SECONDS = 24 * 60 * 60
DEFAULT_IN_PROGRESS_TTL_SECONDS = 60


class IdempotencyState(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ReserveState(StrEnum):
    RESERVED = "reserved"
    REPLAY = "replay"
    MISMATCH = "mismatch"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True, kw_only=True)
class IdempotencyScope:
    """Escopo da chave: tenant + usuario + metodo + rota concreta."""

    company_id: uuid.UUID
    user_id: uuid.UUID
    method: str
    route: str


@dataclass(frozen=True, kw_only=True)
class ReserveResult:
    state: ReserveState
    response_status: int | None = None
    response_body: dict[str, Any] | None = None
    retry_after_seconds: int = 1


class IdempotencyRepository(Protocol):
    """Porta de persistencia atomica das chaves."""

    async def reserve(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> ReserveResult: ...

    async def complete(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        status_code: int,
        body: dict[str, Any] | None,
        expires_at: datetime,
    ) -> bool: ...

    async def release(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
    ) -> bool: ...


class IdempotencyKeyRequiredError(AppError):
    """Mutacao critica sem chave de idempotencia."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "idempotency_key_required"


class IdempotencyKeyInvalidError(AppError):
    """Chave fora do formato (16 a 128 caracteres seguros)."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "idempotency_key_invalid"


class IdempotencyPayloadMismatchError(AppError):
    """Mesma chave reutilizada com payload diferente."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "idempotency_payload_mismatch"


class IdempotencyInProgressError(AppError):
    """Requisicao concorrente com a mesma chave ainda em andamento."""

    status_code = 409
    title = "Conflict"
    code = "idempotency_in_progress"

    def __init__(self, *, retry_after_seconds: int) -> None:
        retry = max(1, retry_after_seconds)
        super().__init__("Requisicao com a mesma Idempotency-Key ainda em andamento.")
        self.headers = {"Retry-After": str(retry)}


def validate_idempotency_key(key: str) -> str:
    """Valida o formato da chave (UUID ou string de 16 a 128 caracteres)."""
    candidate = key.strip()
    if not _KEY_PATTERN.fullmatch(candidate):
        raise IdempotencyKeyInvalidError(
            "Idempotency-Key deve ter de 16 a 128 caracteres (A-Z, a-z, 0-9, ._~:/+=@-)."
        )
    return candidate


@dataclass(frozen=True, kw_only=True)
class BeginResult:
    """Resultado de ``begin``: executar ou devolver resposta gravada."""

    replay: bool
    status_code: int | None = None
    body: dict[str, Any] | None = None


class IdempotencyService:
    """Orquestra reserva, replay, conclusao e liberacao."""

    def __init__(
        self,
        *,
        repository: IdempotencyRepository,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        in_progress_ttl_seconds: int = DEFAULT_IN_PROGRESS_TTL_SECONDS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._ttl = timedelta(seconds=max(1, ttl_seconds))
        self._in_progress_ttl = timedelta(seconds=max(1, in_progress_ttl_seconds))
        self._now = now or (lambda: datetime.now(UTC))

    async def begin(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
    ) -> BeginResult:
        now = self._now()
        result = await self._repository.reserve(
            scope=scope,
            key=key,
            request_hash=request_hash,
            now=now,
            expires_at=now + self._in_progress_ttl,
        )
        if result.state is ReserveState.REPLAY:
            increment_idempotency_request(outcome="replay")
            return BeginResult(
                replay=True,
                status_code=result.response_status,
                body=result.response_body,
            )
        if result.state is ReserveState.MISMATCH:
            increment_idempotency_request(outcome="mismatch")
            raise IdempotencyPayloadMismatchError(
                "A mesma Idempotency-Key foi usada com um payload diferente."
            )
        if result.state is ReserveState.IN_PROGRESS:
            increment_idempotency_request(outcome="in_progress")
            raise IdempotencyInProgressError(retry_after_seconds=result.retry_after_seconds)

        increment_idempotency_request(outcome="new")
        return BeginResult(replay=False)

    async def complete(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        status_code: int,
        body: dict[str, Any] | None,
    ) -> bool:
        now = self._now()
        completed = await self._repository.complete(
            scope=scope,
            key=key,
            request_hash=request_hash,
            status_code=status_code,
            body=body,
            expires_at=now + self._ttl,
        )
        if not completed:  # pragma: no cover - defensivo (corrida/expurgo)
            _logger.warning(
                "idempotency_complete_missed",
                route=scope.route,
                method=scope.method,
            )
        return completed

    async def release(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
    ) -> None:
        try:
            released = await self._repository.release(
                scope=scope, key=key, request_hash=request_hash
            )
        except Exception:  # liberar nunca deve mascarar o erro original
            _logger.exception(
                "idempotency_release_failed",
                route=scope.route,
                method=scope.method,
            )
            return
        if released:
            increment_idempotency_request(outcome="released")
