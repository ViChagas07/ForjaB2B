"""Testes de integracao do store Redis da recuperacao (codigo/reset token)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
import redis.asyncio as redis

from app.modules.identity.application.errors import PasswordRecoveryStoreError
from app.modules.identity.infrastructure.password_recovery_store import (
    RedisPasswordRecoveryStore,
)


@pytest.fixture()
async def recovery_store(
    redis_url: str,
) -> AsyncIterator[RedisPasswordRecoveryStore]:
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        await client.flushdb()
        yield RedisPasswordRecoveryStore(cast(Any, client))
    finally:
        await client.flushdb()
        await cast(Any, client).aclose()


async def test_cooldown_e_reserva_atomica(recovery_store: RedisPasswordRecoveryStore) -> None:
    user_id = uuid.uuid4()

    assert await recovery_store.reserve_resend(user_id=user_id, ttl_seconds=60)
    assert not await recovery_store.reserve_resend(user_id=user_id, ttl_seconds=60)
    await recovery_store.delete_cooldown(user_id=user_id)
    assert await recovery_store.reserve_resend(user_id=user_id, ttl_seconds=60)


async def test_codigo_guardado_apenas_como_digest(
    recovery_store: RedisPasswordRecoveryStore,
) -> None:
    user_id = uuid.uuid4()
    await recovery_store.save_code(
        user_id=user_id, digest="a" * 64, locale="pt-BR", ttl_seconds=600
    )

    state = await recovery_store.load_code(user_id=user_id)
    assert state is not None
    assert state.digest == "a" * 64
    assert state.attempts == 0
    assert state.locale == "pt-BR"


async def test_tentativas_invalidam_codigo_no_limite(
    recovery_store: RedisPasswordRecoveryStore,
) -> None:
    user_id = uuid.uuid4()
    await recovery_store.save_code(user_id=user_id, digest="b" * 64, locale=None, ttl_seconds=600)

    assert await recovery_store.record_failed_attempt(user_id=user_id, max_attempts=2) == 1
    assert await recovery_store.load_code(user_id=user_id) is not None
    assert await recovery_store.record_failed_attempt(user_id=user_id, max_attempts=2) == 2
    assert await recovery_store.load_code(user_id=user_id) is None


async def test_consumo_de_codigo_e_unico_e_exige_digest(
    recovery_store: RedisPasswordRecoveryStore,
) -> None:
    user_id = uuid.uuid4()
    await recovery_store.save_code(user_id=user_id, digest="c" * 64, locale=None, ttl_seconds=600)

    assert not await recovery_store.consume_code(user_id=user_id, digest="d" * 64)
    assert await recovery_store.consume_code(user_id=user_id, digest="c" * 64)
    assert not await recovery_store.consume_code(user_id=user_id, digest="c" * 64)


async def test_reset_token_e_consumido_uma_unica_vez(
    recovery_store: RedisPasswordRecoveryStore,
) -> None:
    token_hash = "e" * 64
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    await recovery_store.save_reset_token(
        token_hash=token_hash,
        user_id=user_id,
        company_id=company_id,
        locale="ar",
        channel="sms",
        ttl_seconds=600,
    )

    data = await recovery_store.consume_reset_token(token_hash=token_hash)
    assert data is not None
    assert data.user_id == user_id
    assert data.company_id == company_id
    assert data.locale == "ar"
    assert data.channel == "sms"
    assert await recovery_store.consume_reset_token(token_hash=token_hash) is None


async def test_probe_e_erros_do_backend_sao_fail_closed() -> None:
    class _BrokenClient:
        async def ping(self) -> bool:
            raise RuntimeError("redis fora")

    store = RedisPasswordRecoveryStore(cast(Any, _BrokenClient()))
    with pytest.raises(PasswordRecoveryStoreError):
        await store.probe()


async def test_tentativas_sms_sao_contadas_e_limpas(
    recovery_store: RedisPasswordRecoveryStore,
) -> None:
    user_id = uuid.uuid4()

    assert await recovery_store.get_sms_attempts(user_id=user_id) == 0
    assert (
        await recovery_store.record_sms_failed_attempt(
            user_id=user_id, max_attempts=3, ttl_seconds=600
        )
        == 1
    )
    assert await recovery_store.get_sms_attempts(user_id=user_id) == 1
    await recovery_store.clear_sms_attempts(user_id=user_id)
    assert await recovery_store.get_sms_attempts(user_id=user_id) == 0
