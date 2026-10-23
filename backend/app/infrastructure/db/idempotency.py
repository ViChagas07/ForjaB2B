"""Repositorio SQLAlchemy das chaves de idempotencia.

Cada operacao abre uma UoW curta com contexto de tenant (RLS). A reserva e
atomica por meio de ``INSERT ... ON CONFLICT DO NOTHING``; a conclusao so
acontece se a linha ainda estiver ``in_progress`` e com o mesmo ``request_hash``
(evita que uma requisicao antiga sobrescreva uma tentativa expirada/reassumida).
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.application.idempotency import (
    IdempotencyScope,
    ReserveResult,
    ReserveState,
)
from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory

_INSERT_RESERVATION = text(
    "INSERT INTO idempotency_keys "
    "(company_id, user_id, method, route, key, request_hash, state, expires_at) "
    "VALUES (:company_id, :user_id, :method, :route, :key, :request_hash, "
    "'in_progress', :expires_at) "
    "ON CONFLICT (company_id, user_id, method, route, key) DO NOTHING "
    "RETURNING id"
)
_SELECT_KEY = text(
    "SELECT state, request_hash, response_status, response_body, expires_at "
    "FROM idempotency_keys "
    "WHERE company_id = :company_id AND user_id = :user_id AND method = :method "
    "AND route = :route AND key = :key"
)
_TAKEOVER = text(
    "UPDATE idempotency_keys SET request_hash = :request_hash, state = 'in_progress', "
    "response_status = NULL, response_body = NULL, created_at = now(), updated_at = now(), "
    "expires_at = :expires_at "
    "WHERE company_id = :company_id AND user_id = :user_id AND method = :method "
    "AND route = :route AND key = :key AND expires_at <= :now "
    "RETURNING id"
)
_COMPLETE = text(
    "UPDATE idempotency_keys SET state = 'completed', response_status = :status, "
    "response_body = CAST(:body AS jsonb), updated_at = now(), expires_at = :expires_at "
    "WHERE company_id = :company_id AND user_id = :user_id AND method = :method "
    "AND route = :route AND key = :key AND state = 'in_progress' "
    "AND request_hash = :request_hash "
    "RETURNING id"
)
_RELEASE = text(
    "DELETE FROM idempotency_keys "
    "WHERE company_id = :company_id AND user_id = :user_id AND method = :method "
    "AND route = :route AND key = :key AND state = 'in_progress' "
    "AND request_hash = :request_hash "
    "RETURNING id"
)


def _scope_params(scope: IdempotencyScope, key: str) -> dict[str, Any]:
    return {
        "company_id": scope.company_id,
        "user_id": scope.user_id,
        "method": scope.method,
        "route": scope.route,
        "key": key,
    }


def _retry_after(row: Any, now: datetime) -> int:
    remaining = float((row.expires_at - now).total_seconds())
    return max(1, math.ceil(remaining))


class SqlAlchemyIdempotencyRepository:
    """Implementacao da porta ``IdempotencyRepository`` sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def reserve(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> ReserveResult:
        tenant = TenantContext(company_id=scope.company_id, user_id=scope.user_id)
        async with self._uow_factory.begin(tenant) as uow:
            for _ in range(2):
                if await self._try_insert(
                    uow, scope=scope, key=key, request_hash=request_hash, expires_at=expires_at
                ):
                    await uow.commit()
                    return ReserveResult(state=ReserveState.RESERVED)

                row = await self._select(uow, scope=scope, key=key)
                if row is None:
                    # Corrida com expurgo/rollback: tenta reservar novamente.
                    continue

                if row.expires_at <= now:
                    taken = await self._takeover(
                        uow,
                        scope=scope,
                        key=key,
                        request_hash=request_hash,
                        now=now,
                        expires_at=expires_at,
                    )
                    await uow.commit()
                    if taken:
                        return ReserveResult(state=ReserveState.RESERVED)
                    return ReserveResult(state=ReserveState.IN_PROGRESS, retry_after_seconds=1)

                await uow.commit()
                return self._result_from_row(row, request_hash=request_hash, now=now)

            await uow.commit()
        return ReserveResult(state=ReserveState.RESERVED)

    async def _try_insert(
        self,
        uow: Any,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        expires_at: datetime,
    ) -> bool:
        inserted = (
            await uow.session.execute(
                _INSERT_RESERVATION,
                {
                    **_scope_params(scope, key),
                    "request_hash": request_hash,
                    "expires_at": expires_at,
                },
            )
        ).first()
        return inserted is not None

    async def _select(self, uow: Any, *, scope: IdempotencyScope, key: str) -> Any:
        return (await uow.session.execute(_SELECT_KEY, _scope_params(scope, key))).first()

    async def _takeover(
        self,
        uow: Any,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        taken = (
            await uow.session.execute(
                _TAKEOVER,
                {
                    **_scope_params(scope, key),
                    "request_hash": request_hash,
                    "expires_at": expires_at,
                    "now": now,
                },
            )
        ).first()
        return taken is not None

    @staticmethod
    def _result_from_row(row: Any, *, request_hash: str, now: datetime) -> ReserveResult:
        if row.state == "completed":
            if row.request_hash != request_hash:
                return ReserveResult(state=ReserveState.MISMATCH)
            body = row.response_body
            if isinstance(body, str):
                body = json.loads(body)
            return ReserveResult(
                state=ReserveState.REPLAY,
                response_status=row.response_status,
                response_body=body,
            )
        return ReserveResult(
            state=ReserveState.IN_PROGRESS,
            retry_after_seconds=_retry_after(row, now),
        )

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
        tenant = TenantContext(company_id=scope.company_id, user_id=scope.user_id)
        async with self._uow_factory.begin(tenant) as uow:
            updated = (
                await uow.session.execute(
                    _COMPLETE,
                    {
                        **_scope_params(scope, key),
                        "request_hash": request_hash,
                        "status": status_code,
                        "body": json.dumps(body, ensure_ascii=False) if body is not None else None,
                        "expires_at": expires_at,
                    },
                )
            ).first()
            await uow.commit()
            return updated is not None

    async def release(
        self,
        *,
        scope: IdempotencyScope,
        key: str,
        request_hash: str,
    ) -> bool:
        tenant = TenantContext(company_id=scope.company_id, user_id=scope.user_id)
        async with self._uow_factory.begin(tenant) as uow:
            deleted = (
                await uow.session.execute(
                    _RELEASE,
                    {**_scope_params(scope, key), "request_hash": request_hash},
                )
            ).first()
            await uow.commit()
            return deleted is not None
