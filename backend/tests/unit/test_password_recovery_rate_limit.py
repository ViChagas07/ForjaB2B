"""Testes dos rate limits dedicados da recuperacao de conta."""

from __future__ import annotations

import math
from typing import Any

import pytest
from structlog.testing import capture_logs

from app.application.rate_limit import (
    DailyQuotaDecision,
    InMemoryBucketStore,
    InMemoryDailyQuotaStore,
    RateLimitBackendError,
    RateLimitClass,
    RateLimitDecision,
    RateLimiter,
    RateLimitPolicy,
)
from app.core.errors import RateLimitExceededError, ServiceUnavailableError
from app.interface.rate_limit import classify_request
from app.modules.identity.application.password_recovery import PasswordRecoveryLimiter

_POLICIES = {
    rate_class: RateLimitPolicy(capacity=2, refill_per_minute=60) for rate_class in RateLimitClass
}


class _Clock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _FailingBucketStore:
    async def consume(
        self,
        *,
        key: str,
        capacity: int,
        refill_per_second: float,
        now: float,
    ) -> tuple[bool, float, float]:
        _ = (key, capacity, refill_per_second, now)
        raise RuntimeError("redis indisponivel")


class _FailingDailyStore:
    async def consume(self, *, key: str, limit: int, ttl_seconds: int) -> DailyQuotaDecision:
        _ = (key, limit, ttl_seconds)
        raise RateLimitBackendError("redis indisponivel")


class _RecordingLimiter:
    def __init__(self) -> None:
        self.calls: list[tuple[RateLimitClass, str, bool]] = []

    async def check(
        self, *, rate_class: RateLimitClass, identity: str, fail_closed: bool
    ) -> RateLimitDecision:
        self.calls.append((rate_class, identity, fail_closed))
        return RateLimitDecision(
            allowed=True,
            limit=10,
            remaining=9,
            retry_after_seconds=0,
            reset_after_seconds=1,
        )


class _RecordingDailyStore:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def consume(self, *, key: str, limit: int, ttl_seconds: int) -> DailyQuotaDecision:
        self.keys.append(key)
        return DailyQuotaDecision(
            allowed=True,
            limit=limit,
            remaining=max(0, limit - 1),
            retry_after_seconds=0,
        )


def _guard(
    *,
    limiter: Any,
    daily_store: Any,
    daily_limit: int = 5,
    enabled: bool = True,
) -> PasswordRecoveryLimiter:
    return PasswordRecoveryLimiter(
        limiter=limiter,
        daily_store=daily_store,
        secret="test-secret",
        daily_limit=daily_limit,
        enabled=enabled,
    )


async def test_fail_closed_do_rate_limiter_levanta_erro_sem_fallback() -> None:
    clock = _Clock()
    limiter = RateLimiter(
        store=_FailingBucketStore(),
        policies=_POLICIES,
        fallback_store=InMemoryBucketStore(),
        clock=clock,
    )

    with capture_logs() as logs:
        for _ in range(2):
            with pytest.raises(RateLimitBackendError):
                await limiter.check(
                    rate_class=RateLimitClass.PASSWORD_RECOVERY,
                    identity="ip:203.0.113.7",
                    fail_closed=True,
                )

    rendered = str(logs)
    assert "203.0.113.7" not in rendered


async def test_ip_limitado_com_429_e_retry_after() -> None:
    clock = _Clock()
    limiter = RateLimiter(store=InMemoryBucketStore(), policies=_POLICIES, clock=clock)
    guard = _guard(limiter=limiter, daily_store=InMemoryDailyQuotaStore(clock=clock))

    await guard.check_ip("203.0.113.7")
    await guard.check_ip("203.0.113.7")
    with pytest.raises(RateLimitExceededError) as excinfo:
        await guard.check_ip("203.0.113.7")

    error = excinfo.value
    assert error.retry_after_seconds >= 1
    assert error.headers is not None
    assert error.headers["Retry-After"] == str(error.retry_after_seconds)
    assert error.headers["RateLimit-Limit"] == "2"


async def test_identificador_usa_hmac_e_nao_valor_em_claro() -> None:
    limiter = _RecordingLimiter()
    daily = _RecordingDailyStore()
    guard = _guard(limiter=limiter, daily_store=daily)

    await guard.check_identifier(kind="email", value="User@Example.com")

    assert len(limiter.calls) == 1
    _, identity, fail_closed = limiter.calls[0]
    assert fail_closed is True
    assert "User@Example.com" not in identity
    assert "user@example.com" not in identity
    assert len(identity.split(":", 1)[1]) == 64
    assert "user@example.com" not in daily.keys[0]


async def test_baldes_de_recuperacao_sao_separados_de_auth() -> None:
    limiter = _RecordingLimiter()
    guard = _guard(limiter=limiter, daily_store=_RecordingDailyStore())

    await guard.check_ip("198.51.100.10")
    await guard.check_identifier(kind="phone", value="+5511999999999")

    classes = [call[0] for call in limiter.calls]
    assert classes == [
        RateLimitClass.PASSWORD_RECOVERY,
        RateLimitClass.PASSWORD_RECOVERY_IDENTIFIER,
    ]
    assert RateLimitClass.AUTH not in classes


async def test_teto_diario_por_identificador() -> None:
    clock = _Clock()
    policies = dict(_POLICIES)
    policies[RateLimitClass.PASSWORD_RECOVERY_IDENTIFIER] = RateLimitPolicy(
        capacity=10, refill_per_minute=60
    )
    limiter = RateLimiter(store=InMemoryBucketStore(), policies=policies, clock=clock)
    guard = _guard(
        limiter=limiter,
        daily_store=InMemoryDailyQuotaStore(clock=clock),
        daily_limit=2,
    )

    await guard.check_identifier(kind="email", value="user@example.com")
    await guard.check_identifier(kind="email", value="user@example.com")
    with pytest.raises(RateLimitExceededError) as excinfo:
        await guard.check_identifier(kind="email", value="user@example.com")

    assert excinfo.value.retry_after_seconds >= 1


async def test_redis_indisponivel_no_guard_vira_503_generico() -> None:
    limiter = RateLimiter(
        store=_FailingBucketStore(),
        policies=_POLICIES,
        fallback_store=InMemoryBucketStore(),
        clock=_Clock(),
    )
    guard = _guard(limiter=limiter, daily_store=InMemoryDailyQuotaStore())

    with pytest.raises(ServiceUnavailableError) as excinfo:
        await guard.check_ip("203.0.113.7")

    assert "redis" not in str(excinfo.value).lower()


async def test_falha_do_teto_diario_vira_503_generico() -> None:
    guard = _guard(
        limiter=RateLimiter(store=InMemoryBucketStore(), policies=_POLICIES, clock=_Clock()),
        daily_store=_FailingDailyStore(),
    )

    with pytest.raises(ServiceUnavailableError) as excinfo:
        await guard.check_identifier(kind="email", value="user@example.com")

    assert "redis" not in str(excinfo.value).lower()


async def test_guard_desabilitado_nao_consome_nada() -> None:
    limiter = _RecordingLimiter()
    daily = _RecordingDailyStore()
    guard = _guard(limiter=limiter, daily_store=daily, enabled=False)

    await guard.check_ip("203.0.113.7")
    await guard.check_identifier(kind="email", value="user@example.com")

    assert limiter.calls == []
    assert daily.keys == []


async def test_cota_diaria_memoria_reseta_apos_ttl() -> None:
    clock = _Clock()
    store = InMemoryDailyQuotaStore(clock=clock)

    first = await store.consume(key="k", limit=1, ttl_seconds=86_400)
    second = await store.consume(key="k", limit=1, ttl_seconds=86_400)
    clock.advance(86_401)
    third = await store.consume(key="k", limit=1, ttl_seconds=86_400)

    assert first.allowed is True
    assert second.allowed is False
    assert second.retry_after_seconds == math.ceil(86_400)
    assert third.allowed is True


def test_classificacao_ignora_recuperacao_e_mantem_auth() -> None:
    assert classify_request("/api/v1/auth/password-recovery/request", "POST") is None
    assert classify_request("/api/v1/auth/login", "POST") == RateLimitClass.AUTH
    assert classify_request("/api/v1/auth/refresh", "POST") == RateLimitClass.AUTH
