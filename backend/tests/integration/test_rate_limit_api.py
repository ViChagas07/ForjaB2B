"""Testes de integracao do rate limiting com Redis real (Testcontainers)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import redis.asyncio as redis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.rate_limit import (
    InMemoryBucketStore,
    RateLimitClass,
    RateLimiter,
    RateLimitPolicy,
)
from app.application.security import TokenService
from app.core.config import Settings
from app.infrastructure.rate_limit import RedisBucketStore, RedisFailureStore
from app.interface.rate_limit import RateLimitMiddleware


@pytest.fixture()
async def redis_client(redis_url: str) -> AsyncIterator[redis.Redis[str]]:
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def test_token_bucket_atomico_no_redis(redis_client: redis.Redis[str]) -> None:
    store = RedisBucketStore(redis_client)
    now = 1_000_000.0
    policy = RateLimitPolicy(capacity=2, refill_per_minute=60)
    key = "test:rl:atomic"

    first = await store.consume(
        key=key, capacity=policy.capacity, refill_per_second=policy.refill_per_second, now=now
    )
    second = await store.consume(
        key=key, capacity=policy.capacity, refill_per_second=policy.refill_per_second, now=now
    )
    third = await store.consume(
        key=key, capacity=policy.capacity, refill_per_second=policy.refill_per_second, now=now
    )
    after = await store.consume(
        key=key,
        capacity=policy.capacity,
        refill_per_second=policy.refill_per_second,
        now=now + 61,
    )

    assert first[0] and second[0]
    assert not third[0]
    assert third[2] >= 1
    assert after[0]


async def test_falha_de_redis_cai_para_limitador_local() -> None:
    bad_client = redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    limiter = RateLimiter(
        store=RedisBucketStore(bad_client),
        policies={
            RateLimitClass.SEARCH: RateLimitPolicy(capacity=1, refill_per_minute=60),
        },
        fallback_store=InMemoryBucketStore(),
    )
    try:
        first = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
        second = await limiter.check(rate_class=RateLimitClass.SEARCH, identity="ip:1")
    finally:
        await bad_client.aclose()

    assert first.allowed
    assert not second.allowed


async def test_failure_store_redis_bloqueia_e_limpa(redis_client: redis.Redis[str]) -> None:
    store = RedisFailureStore(redis_client)
    key = "test:login:fail"
    await redis_client.delete(key)
    now = 1_000_000.0

    assert await store.blocked_for(key=key, now=now) == 0
    first = await store.record_failure(
        key=key,
        now=now,
        ttl_seconds=900,
        threshold=2,
        base_backoff_seconds=30,
        max_backoff_seconds=900,
    )
    second = await store.record_failure(
        key=key,
        now=now,
        ttl_seconds=900,
        threshold=2,
        base_backoff_seconds=30,
        max_backoff_seconds=900,
    )
    assert first == 0
    assert second >= 30
    assert await store.blocked_for(key=key, now=now) >= 30

    await store.clear(key=key)
    assert await store.blocked_for(key=key, now=now) == 0


async def test_middleware_429_com_redis(redis_client: redis.Redis[str]) -> None:
    settings = Settings(environment="test", otel_enabled=False, rate_limit_enabled=True)
    limiter = RateLimiter(
        store=RedisBucketStore(redis_client),
        policies={
            RateLimitClass.PUBLIC_READ: RateLimitPolicy(capacity=1, refill_per_minute=1),
        },
        fallback_store=InMemoryBucketStore(),
    )
    token_service = TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )
    app = FastAPI()

    @app.get("/api/v1/catalog/products")
    async def products() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        settings=settings,
        token_service=token_service,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/api/v1/catalog/products")
        second = await client.get("/api/v1/catalog/products")

    assert first.status_code == 200
    assert first.headers["ratelimit-remaining"] == "0"
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1
