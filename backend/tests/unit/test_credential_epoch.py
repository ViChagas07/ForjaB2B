"""Testes da epoca de credencial: cache Redis, fallback DB e fail-closed."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from structlog.testing import capture_logs

from app.application.security import CredentialEpochUnavailableError
from app.infrastructure.security.credential_epoch import (
    CredentialEpochSessionRevoker,
    SqlAlchemyRedisCredentialEpochResolver,
)

_USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
_COMPANY_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class _FakeRedis:
    def __init__(
        self,
        *,
        value: str | None = None,
        get_error: Exception | None = None,
        set_error: Exception | None = None,
    ) -> None:
        self.value = value
        self.get_error = get_error
        self.set_error = set_error
        self.gets: list[str] = []
        self.sets: list[tuple[str, str, int | None]] = []

    async def get(self, key: str) -> str | None:
        self.gets.append(key)
        if self.get_error is not None:
            raise self.get_error
        return self.value

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.sets.append((key, value, ex))
        if self.set_error is not None:
            raise self.set_error


class _Result:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def first(self) -> tuple[Any, ...] | None:
        return self._row


class _Session:
    def __init__(self, row: tuple[Any, ...] | None, error: Exception | None) -> None:
        self._row = row
        self._error = error
        self.executed = 0

    async def execute(self, statement: object, params: object) -> _Result:
        _ = (statement, params)
        self.executed += 1
        if self._error is not None:
            raise self._error
        return _Result(self._row)


class _Uow:
    def __init__(self, row: tuple[Any, ...] | None, error: Exception | None) -> None:
        self.session = _Session(row, error)
        self.committed = False

    async def __aenter__(self) -> _Uow:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        _ = (exc_type, exc, tb)
        return False

    async def commit(self) -> None:
        self.committed = True


class _Factory:
    def __init__(self, row: tuple[Any, ...] | None, error: Exception | None = None) -> None:
        self.row = row
        self.error = error
        self.calls = 0
        self.uow: _Uow | None = None

    def begin(self, tenant: object) -> _Uow:
        _ = tenant
        self.calls += 1
        self.uow = _Uow(self.row, self.error)
        return self.uow


def _resolver(
    redis_client: _FakeRedis,
    factory: _Factory,
    *,
    ttl_seconds: int = 60,
) -> SqlAlchemyRedisCredentialEpochResolver:
    return SqlAlchemyRedisCredentialEpochResolver(
        redis_client=cast(Any, redis_client),
        uow_factory=cast(Any, factory),
        ttl_seconds=ttl_seconds,
    )


async def test_cache_hit_nao_vai_ao_banco() -> None:
    redis_client = _FakeRedis(value="3")
    factory = _Factory((9,))
    resolver = _resolver(redis_client, factory)

    assert await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID) == 3
    assert factory.calls == 0
    assert redis_client.sets == []


async def test_cache_miss_le_banco_e_repopula_cache() -> None:
    redis_client = _FakeRedis(value=None)
    factory = _Factory((2,))
    resolver = _resolver(redis_client, factory)

    assert await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID) == 2
    assert factory.calls == 1
    assert redis_client.sets == [(f"credential_epoch:{_USER_ID}", "2", 60)]
    assert factory.uow is not None and factory.uow.committed is True


async def test_sem_linha_no_banco_e_epoca_zero() -> None:
    resolver = _resolver(_FakeRedis(value=None), _Factory(None))
    assert await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID) == 0


async def test_redis_fora_usa_banco() -> None:
    redis_client = _FakeRedis(get_error=RuntimeError("redis fora"))
    factory = _Factory((4,))
    resolver = _resolver(redis_client, factory)

    with capture_logs() as logs:
        epoch = await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID)

    assert epoch == 4
    assert factory.calls == 1
    assert str(_USER_ID) not in str(logs)


async def test_cache_malformado_usa_banco() -> None:
    resolver = _resolver(_FakeRedis(value="nao-e-int"), _Factory((5,)))
    assert await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID) == 5


async def test_falha_de_escrita_do_cache_nao_falha() -> None:
    redis_client = _FakeRedis(value=None, set_error=RuntimeError("redis fora"))
    resolver = _resolver(redis_client, _Factory((6,)))

    assert await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID) == 6


async def test_banco_fora_falha_fechado_503() -> None:
    resolver = _resolver(
        _FakeRedis(value=None, get_error=RuntimeError("redis fora")),
        _Factory(None, RuntimeError("db fora")),
    )

    with pytest.raises(CredentialEpochUnavailableError) as excinfo:
        await resolver.resolve(user_id=_USER_ID, company_id=_COMPANY_ID)

    assert excinfo.value.status_code == 503


async def test_revogador_atualiza_cache_com_nova_epoca() -> None:
    redis_client = _FakeRedis()
    revoker = CredentialEpochSessionRevoker(redis_client=cast(Any, redis_client), ttl_seconds=60)

    await revoker.revoke_all_for_user(user_id=_USER_ID, company_id=_COMPANY_ID, credential_epoch=7)

    assert redis_client.sets == [(f"credential_epoch:{_USER_ID}", "7", 60)]


@pytest.mark.asyncio
async def test_revogador_com_redis_fora_levanta_erro_sem_pii() -> None:
    redis_client = _FakeRedis(set_error=RuntimeError("redis fora"))
    revoker = CredentialEpochSessionRevoker(redis_client=cast(Any, redis_client))

    with capture_logs() as logs, pytest.raises(RuntimeError):
        await revoker.revoke_all_for_user(
            user_id=_USER_ID, company_id=_COMPANY_ID, credential_epoch=7
        )

    assert str(_USER_ID) not in str(logs)
