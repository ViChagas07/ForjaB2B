"""Testes de rate limiting: token bucket, fail-open, isolamento e 429."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI

from app.application.rate_limit import (
    InMemoryBucketStore,
    InMemoryFailureStore,
    LoginThrottle,
    RateLimitClass,
    RateLimiter,
    RateLimitPolicy,
)
from app.application.security import TokenService
from app.core.config import Settings
from app.core.request_context import client_ip, request_scheme
from app.interface.rate_limit import RateLimitMiddleware, classify_request

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


class _FailingStore:
    async def consume(self, **_: object) -> tuple[bool, float, float]:
        raise RuntimeError("redis indisponivel")


async def test_token_bucket_respeita_limite_e_recupera_com_tempo() -> None:
    clock = _Clock()
    limiter = RateLimiter(store=InMemoryBucketStore(), policies=_POLICIES, clock=clock)

    first = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
    second = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
    third = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")

    assert first.allowed and second.allowed
    assert not third.allowed
    assert third.retry_after_seconds >= 1
    assert third.limit == 2

    clock.advance(1.0)
    recovered = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
    assert recovered.allowed


async def test_isolamento_por_usuario_e_por_ip() -> None:
    clock = _Clock()
    limiter = RateLimiter(store=InMemoryBucketStore(), policies=_POLICIES, clock=clock)

    assert (await limiter.check(rate_class=RateLimitClass.AUTHENTICATED, identity="user:a")).allowed
    assert (await limiter.check(rate_class=RateLimitClass.AUTHENTICATED, identity="user:a")).allowed
    assert not (
        await limiter.check(rate_class=RateLimitClass.AUTHENTICATED, identity="user:a")
    ).allowed

    assert (await limiter.check(rate_class=RateLimitClass.AUTHENTICATED, identity="user:b")).allowed
    assert (
        await limiter.check(rate_class=RateLimitClass.AUTHENTICATED, identity="ip:1.2.3.4")
    ).allowed


async def test_falha_do_redis_faz_fail_open_com_limitador_local() -> None:
    clock = _Clock()
    fallback = InMemoryBucketStore()
    limiter = RateLimiter(
        store=_FailingStore(),  # type: ignore[arg-type]
        policies=_POLICIES,
        fallback_store=fallback,
        clock=clock,
    )

    first = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
    second = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
    third = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")

    assert first.allowed and second.allowed
    assert not third.allowed
    # O fallback local continua ativo e recupera com o tempo.
    clock.advance(1.0)
    assert (await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")).allowed


async def test_login_throttle_bloqueia_progressivamente_sem_revelar_conta() -> None:
    clock = _Clock()
    throttle = LoginThrottle(
        store=InMemoryFailureStore(),
        fallback_store=InMemoryFailureStore(),
        secret="segredo-de-teste",  # noqa: S106 - valor efemero de teste
        ttl_seconds=900,
        threshold=3,
        base_backoff_seconds=30,
        max_backoff_seconds=900,
        clock=clock,
    )

    assert await throttle.blocked_for(email="Existe@Teste.com", client_ip="1.1.1.1") == 0
    assert await throttle.record_failure(email="Existe@Teste.com", client_ip="1.1.1.1") == 0
    assert await throttle.record_failure(email="existe@teste.com", client_ip="1.1.1.1") == 0
    blocked = await throttle.record_failure(email="existe@teste.com", client_ip="1.1.1.1")
    assert blocked >= 30
    assert await throttle.blocked_for(email="existe@teste.com", client_ip="1.1.1.1") >= 30

    # A mesma sequencia para um e-mail inexistente tem o mesmo comportamento.
    for _ in range(3):
        await throttle.record_failure(email="nao-existe@teste.com", client_ip="1.1.1.1")
    assert await throttle.blocked_for(email="nao-existe@teste.com", client_ip="1.1.1.1") >= 30


class _DenyingLimiter:
    async def check(self, **_: object) -> Any:
        from app.application.rate_limit import RateLimitDecision

        return RateLimitDecision(
            allowed=False,
            limit=3,
            remaining=0,
            retry_after_seconds=7,
            reset_after_seconds=10,
        )


async def test_middleware_retorna_429_com_retry_after() -> None:
    app = FastAPI()

    @app.get("/api/v1/catalog/products")
    async def products() -> dict[str, bool]:
        return {"ok": True}

    settings = Settings(environment="test", otel_enabled=False, rate_limit_enabled=True)
    token_service = TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limiter=_DenyingLimiter(),
        settings=settings,
        token_service=token_service,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/catalog/products")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "7"
    assert response.headers["ratelimit-limit"] == "3"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "urn:forja:problem:rate_limit_exceeded"


def test_erro_429_inclui_rate_limit_e_retry_after() -> None:
    from app.core.errors import RateLimitExceededError

    error = RateLimitExceededError(
        retry_after_seconds=7, limit=5, remaining=0, reset_after_seconds=30
    )
    assert error.status_code == 429
    assert error.headers == {
        "Retry-After": "7",
        "RateLimit-Limit": "5",
        "RateLimit-Remaining": "0",
        "RateLimit-Reset": "30",
    }


def test_classificacao_de_rotas() -> None:
    assert classify_request("/health/ready", "GET") is None
    assert classify_request("/metrics", "GET") is None
    assert classify_request("/api/v1/auth/login", "POST") is RateLimitClass.AUTH
    assert classify_request("/api/v1/companies", "POST") is RateLimitClass.REGISTRATION
    assert classify_request("/api/v1/search/products", "GET") is RateLimitClass.SEARCH
    assert classify_request("/api/v1/admin/catalog/products", "POST") is RateLimitClass.ADMIN_WRITE
    assert classify_request("/api/v1/orders", "POST") is RateLimitClass.AUTHENTICATED
    assert classify_request("/api/v1/catalog/products", "GET") is RateLimitClass.PUBLIC_READ
    assert classify_request("/docs", "GET") is None


def test_ip_real_so_confia_em_proxy_configurado() -> None:
    scope = {
        "type": "http",
        "client": ("10.0.0.5", 1234),
        "headers": [
            (b"x-forwarded-for", b"203.0.113.9, 10.0.0.1"),
            (b"x-forwarded-proto", b"https"),
        ],
    }

    assert client_ip(scope, 0) == "10.0.0.5"
    assert client_ip(scope, 2) == "203.0.113.9"
    assert client_ip(scope, 3) == "10.0.0.5"
    assert request_scheme(scope, 0) == "http"
    assert request_scheme(scope, 1) == "https"

    invalid = {
        "type": "http",
        "client": ("10.0.0.5", 1234),
        "headers": [(b"x-forwarded-for", b"nao-e-ip")],
    }
    assert client_ip(invalid, 1) == "10.0.0.5"
