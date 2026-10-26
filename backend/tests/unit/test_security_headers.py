"""Testes do middleware de cabecalhos de seguranca do backend."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from starlette.responses import PlainTextResponse

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.interface.security_headers import SecurityHeadersMiddleware
from app.main import create_app


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"environment": "test", "otel_enabled": False}
    values.update(overrides)
    return Settings(**values)


@pytest.fixture()
async def app_client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_headers_presentes_em_health(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "server" not in response.headers
    assert "x-powered-by" not in response.headers


async def test_resposta_autenticada_sensivel_tem_no_store(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/api/v1/companies/me")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


async def test_resposta_com_authorization_tem_no_store(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get(
        "/health/live", headers={"Authorization": "Bearer token-invalido"}
    )

    assert response.headers["cache-control"] == "no-store"


async def test_hsts_somente_em_producao_https() -> None:
    app = create_app(_settings(environment="production", security_hsts_enabled=True))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client:
            https_response = await client.get("/health/live")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            http_response = await client.get("/health/live")
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)

    assert https_response.headers["strict-transport-security"].startswith("max-age=31536000")
    assert "includeSubDomains" in https_response.headers["strict-transport-security"]
    assert "strict-transport-security" not in http_response.headers


async def test_hsts_nao_aparece_fora_de_producao() -> None:
    app = create_app(_settings(environment="development"))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client:
            response = await client.get("/health/live")
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)

    assert "strict-transport-security" not in response.headers


async def test_static_permite_embed_cross_origin() -> None:
    app = FastAPI()

    @app.get("/static/catalog/protecao-maos.svg")
    async def static_asset() -> PlainTextResponse:
        return PlainTextResponse("<svg/>")

    @app.get("/api/v1/catalog/products")
    async def api_route() -> PlainTextResponse:
        return PlainTextResponse("[]")

    app.add_middleware(SecurityHeadersMiddleware, settings=_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        static_response = await client.get("/static/catalog/protecao-maos.svg")
        api_response = await client.get("/api/v1/catalog/products")

    assert static_response.headers["cross-origin-resource-policy"] == "cross-origin"
    assert api_response.headers["cross-origin-resource-policy"] == "same-site"


async def test_remove_server_e_x_powered_by_do_app() -> None:
    app = FastAPI()

    @app.get("/")
    async def index() -> PlainTextResponse:
        return PlainTextResponse("ok", headers={"Server": "uvicorn/9.9", "X-Powered-By": "FastAPI"})

    app.add_middleware(SecurityHeadersMiddleware, settings=_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "server" not in response.headers
    assert "x-powered-by" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
