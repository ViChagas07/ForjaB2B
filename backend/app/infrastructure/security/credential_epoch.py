"""Epoca de credencial: cache Redis e leitura RLS no PostgreSQL.

O access token carrega ``cep`` (epoca de emissao). A cada requisicao a epoca
atual e lida primeiro no Redis (TTL curto) e, em caso de miss, no banco com o
tenant do proprio token. Se o cache falhar, o banco resolve; se ambos falharem,
a requisicao e negada com 503 (fail-closed).

O reset grava a nova epoca no banco na mesma transacao da senha e, depois do
commit, atualiza/limpa o cache. Refresh tokens guardam a epoca de emissao e sao
recusados quando ficam atras da atual; nao e necessario um indice por usuario.
"""

from __future__ import annotations

import uuid

import redis.asyncio as redis
from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.application.security import CredentialEpochUnavailableError
from app.core.logging import get_logger
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.ports import PasswordResetSessionRevoker

_logger = get_logger(__name__)

_EPOCH_PREFIX = "credential_epoch:"
_DEFAULT_TTL_SECONDS = 60

_SELECT_EPOCH = text(
    "SELECT credential_epoch FROM user_credential_state "
    "WHERE user_id = :user_id AND company_id = :company_id"
)


def _key(user_id: uuid.UUID) -> str:
    return f"{_EPOCH_PREFIX}{user_id}"


class SqlAlchemyRedisCredentialEpochResolver:
    """Resolve a epoca via cache Redis, com fallback RLS para o banco."""

    def __init__(
        self,
        *,
        redis_client: redis.Redis,
        uow_factory: SqlAlchemyUnitOfWorkFactory,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._uow_factory = uow_factory
        self._ttl_seconds = ttl_seconds

    async def resolve(self, *, user_id: uuid.UUID, company_id: uuid.UUID) -> int:
        cached = await self._read_cache(user_id)
        if cached is not None:
            return cached
        epoch = await self._read_db(user_id=user_id, company_id=company_id)
        await self._write_cache(user_id=user_id, epoch=epoch)
        return epoch

    async def _read_cache(self, user_id: uuid.UUID) -> int | None:
        try:
            raw = await self._redis.get(_key(user_id))
        except Exception as exc:  # noqa: BLE001 - cache best-effort
            _logger.warning("credential_epoch_cache_unavailable", error_type=type(exc).__name__)
            return None
        if raw is None:
            return None
        try:
            epoch = int(raw)
        except (TypeError, ValueError):
            return None
        return epoch if epoch >= 0 else None

    async def _read_db(self, *, user_id: uuid.UUID, company_id: uuid.UUID) -> int:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        try:
            async with self._uow_factory.begin(tenant) as uow:
                row = (
                    await uow.session.execute(
                        _SELECT_EPOCH,
                        {"user_id": user_id, "company_id": company_id},
                    )
                ).first()
                await uow.commit()
        except Exception as exc:
            _logger.warning("credential_epoch_db_unavailable", error_type=type(exc).__name__)
            raise CredentialEpochUnavailableError() from exc
        if row is None:
            return 0
        try:
            return max(0, int(row[0]))
        except (TypeError, ValueError):
            return 0

    async def _write_cache(self, *, user_id: uuid.UUID, epoch: int) -> None:
        try:
            await self._redis.set(_key(user_id), str(epoch), ex=self._ttl_seconds)
        except Exception as exc:  # noqa: BLE001 - cache best-effort
            _logger.warning("credential_epoch_cache_write_failed", error_type=type(exc).__name__)


class CredentialEpochSessionRevoker(PasswordResetSessionRevoker):
    """Atualiza o cache da epoca apos o reset (revoga sessoes antigas).

    O banco ja recebeu a nova epoca na transacao do reset. Este passo apenas
    antecipa a convergencia do cache; falha aqui nao desfaz a senha.
    """

    def __init__(
        self,
        *,
        redis_client: redis.Redis,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    async def revoke_all_for_user(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        credential_epoch: int,
    ) -> None:
        _ = company_id
        try:
            await self._redis.set(_key(user_id), str(credential_epoch), ex=self._ttl_seconds)
        except Exception as exc:
            _logger.warning("credential_epoch_cache_write_failed", error_type=type(exc).__name__)
            raise RuntimeError("credential epoch cache unavailable") from exc
