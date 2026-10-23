"""Integracao HTTP da idempotencia (header, fingerprint e replay).

O guard e usado explicitamente por endpoints de mutacao critica:

    guard = IdempotencyGuard(request=request, auth=auth, service=service, required=True)
    replay = await guard.start()
    if replay is not None:
        return replay
    try:
        result = await use_case(...)
    except Exception:
        await guard.release()
        raise
    response = to_response(result)
    await guard.complete(201, response.model_dump(mode="json"))
    return response

O corpo bruto e lido antes de qualquer parse para calcular o hash. JSON e
canonicalizado quando valido (ordem de chaves/espacos nao mudam a identidade
semantica do payload).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.application.idempotency import (
    IDEMPOTENCY_HEADER,
    IdempotencyKeyInvalidError,
    IdempotencyKeyRequiredError,
    IdempotencyScope,
    IdempotencyService,
    validate_idempotency_key,
)
from app.application.security import AuthContext
from app.core.logging import get_logger

_logger = get_logger(__name__)


def get_idempotency_service(request: Request) -> IdempotencyService:
    return cast(IdempotencyService, request.app.state.idempotency_service)


async def request_fingerprint(request: Request) -> str:
    """SHA-256 do corpo canonicalizado (JSON) ou dos bytes originais."""
    raw = await request.body()
    if not raw:
        return hashlib.sha256(b"").hexdigest()
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        canonical = raw
    else:
        canonical = json.dumps(
            parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _legacy_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if len(candidate) > 128:
        raise IdempotencyKeyInvalidError("Idempotency-Key deve ter de 16 a 128 caracteres.")
    return candidate


def _replay_response(*, status_code: int | None, body: dict[str, Any] | None) -> Response:
    status = status_code or 200
    headers = {"Idempotent-Replayed": "true"}
    if status == 204 or body is None:
        return Response(status_code=status, headers=headers)
    return JSONResponse(content=body, status_code=status, headers=headers)


class IdempotentReplay(Exception):
    """Sinaliza que a resposta original deve ser devolvida sem reexecutar."""

    def __init__(self, response: Response) -> None:
        super().__init__("idempotent replay")
        self.response = response


class IdempotencyGuard:
    """Ciclo de vida da chave para um endpoint."""

    def __init__(
        self,
        *,
        request: Request,
        auth: AuthContext,
        service: IdempotencyService,
        required: bool,
        legacy_key: str | None = None,
    ) -> None:
        self._request = request
        self._auth = auth
        self._service = service
        self._required = required
        self._legacy_key = legacy_key
        self.key: str | None = None
        self.request_hash: str | None = None
        self.scope: IdempotencyScope | None = None

    async def start(self) -> None:
        """Reserva a chave; levanta ``IdempotentReplay`` em caso de replay."""
        header_key = self._request.headers.get(IDEMPOTENCY_HEADER)
        key: str | None
        if header_key is not None:
            key = validate_idempotency_key(header_key)
        else:
            key = _legacy_key(self._legacy_key)
            if key is None:
                if self._required:
                    raise IdempotencyKeyRequiredError(
                        "Envie o header Idempotency-Key (16 a 128 caracteres)."
                    )
                return

        self.key = key
        self.request_hash = await request_fingerprint(self._request)
        self.scope = IdempotencyScope(
            company_id=self._auth.company_id,
            user_id=self._auth.user_id,
            method=self._request.method.upper(),
            route=self._request.url.path,
        )
        result = await self._service.begin(
            scope=self.scope,
            key=key,
            request_hash=self.request_hash,
        )
        if result.replay:
            raise IdempotentReplay(
                _replay_response(status_code=result.status_code, body=result.body)
            )

    async def complete(self, status_code: int, body: dict[str, Any] | None) -> None:
        if self.key is None or self.request_hash is None or self.scope is None:
            return
        try:
            await self._service.complete(
                scope=self.scope,
                key=self.key,
                request_hash=self.request_hash,
                status_code=status_code,
                body=body,
            )
        except Exception:  # o recurso ja foi criado; nao falhar a resposta
            _logger.exception(
                "idempotency_complete_failed",
                route=self.scope.route,
                method=self.scope.method,
            )

    async def release(self) -> None:
        if self.key is None or self.request_hash is None or self.scope is None:
            return
        await self._service.release(scope=self.scope, key=self.key, request_hash=self.request_hash)
