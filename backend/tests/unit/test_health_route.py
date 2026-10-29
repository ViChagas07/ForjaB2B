"""Testes do /health minimo (GET e HEAD) sem banco, Redis ou Elasticsearch."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.core.logging import HealthAccessLogFilter
from app.infrastructure.cache.redis import close_redis_client
from app.interface.health import router
from app.interface.rate_limit import classify_request
from app.main import create_app


@pytest.fixture()
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


@pytest.fixture()
async def full_client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(
        Settings(environment="test", otel_enabled=False, log_format="json", log_level="INFO")
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_health_get_retorna_status_ok_sem_dependencias(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_head_retorna_200(client: httpx.AsyncClient) -> None:
    response = await client.head("/health")

    assert response.status_code == 200


async def test_health_atravessa_middlewares_da_app(full_client: httpx.AsyncClient) -> None:
    get_response = await full_client.get("/health")
    head_response = await full_client.head("/health")

    assert get_response.status_code == 200
    assert get_response.json() == {"status": "ok"}
    assert head_response.status_code == 200


def test_health_isento_de_rate_limit_para_get_e_head() -> None:
    assert classify_request("/health", "GET") is None
    assert classify_request("/health", "HEAD") is None


def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1", "GET", path, "1.1", 200),
        exc_info=None,
    )


def test_filtro_remove_acesso_de_liveness_do_log() -> None:
    access_filter = HealthAccessLogFilter()

    assert access_filter.filter(_access_record("/health")) is False
    assert access_filter.filter(_access_record("/health/live")) is False
    assert access_filter.filter(_access_record("/health/ready")) is True
    assert access_filter.filter(_access_record("/api/v1/catalog/products")) is True
