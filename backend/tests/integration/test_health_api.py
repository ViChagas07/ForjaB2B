"""Testes de integracao da aplicacao FastAPI sobre infraestrutura real.

Sobe a app factory apontando para PostgreSQL e Redis descartaveis
(Testcontainers) e valida startup, health endpoints, correlacao e RFC 7807.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import PostgresDsn

from app.core.config import Settings
from app.core.errors import AppError
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

_JSON_SUFFIX = "application/problem+json"


@pytest.fixture()
async def api_client(test_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_aplicacao_inicia_e_expoe_rotas_base(api_client: httpx.AsyncClient) -> None:
    openapi = await api_client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/health/live" in paths
    assert "/health/ready" in paths


async def test_health_live(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_health_alias_do_docker(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_health_ready_com_dependencias_saudaveis(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }


async def test_health_ready_sem_banco_retorna_503(redis_url: str) -> None:
    """Readiness falha deterministicamente quando o PostgreSQL esta fora."""
    from pydantic import RedisDsn

    settings = Settings(
        environment="test",
        database_url=PostgresDsn(
            "postgresql+asyncpg://forja_app:forja_app_secret_dev@127.0.0.1:9/forja_db"
        ),
        redis_url=RedisDsn(redis_url),
        otel_enabled=False,
        log_format="json",
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "error"
    assert body["checks"]["redis"] == "ok"


async def test_health_ready_sem_redis_retorna_503(app_database_url: str) -> None:
    """Readiness falha quando o Redis esta fora, com o banco saudavel."""
    from pydantic import RedisDsn

    settings = Settings(
        environment="test",
        database_url=PostgresDsn(app_database_url),
        redis_url=RedisDsn("redis://127.0.0.1:9/0"),
        otel_enabled=False,
        log_format="json",
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "error"


async def test_request_id_gerado_e_devolvido(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health/live")
    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    assert len(request_id) == 32


async def test_request_id_propagado_do_header(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health/live", headers={"X-Request-ID": "req-externo-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-externo-123"


async def test_404_retorna_problem_details(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/recurso-inexistente")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith(_JSON_SUFFIX)
    body = response.json()
    assert body["type"] == "urn:forja:problem:http_404"
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert body["instance"] == "/api/v1/recurso-inexistente"
    assert "trace_id" in body


async def test_app_error_mapeado_para_problem_details(test_settings: Settings) -> None:
    """AppError de aplicacao vira Problem Details sem vazar detalhe interno."""

    class SaldoInsuficienteFake(AppError):
        status_code = 422
        title = "Unprocessable Entity"
        code = "saldo_insuficiente_fake"

    app = create_app(test_settings)

    @app.get("/__test-app-error", include_in_schema=False)
    async def _boom() -> None:
        raise SaldoInsuficienteFake("detalhe controlado")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/__test-app-error")
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(_JSON_SUFFIX)
    body = response.json()
    assert body["type"] == "urn:forja:problem:saldo_insuficiente_fake"
    assert body["detail"] == "detalhe controlado"
    assert body["instance"] == "/__test-app-error"


async def test_erro_nao_tratado_nao_vaza_stack(test_settings: Settings) -> None:
    app = create_app(test_settings)

    @app.get("/__test-unhandled", include_in_schema=False)
    async def _boom() -> None:
        raise RuntimeError("detalhe interno sensivel com senha=abc123")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/__test-unhandled")
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)

    assert response.status_code == 500
    body = json.loads(response.content)
    assert body["type"] == "urn:forja:problem:internal_error"
    assert "senha" not in response.text
    assert "Traceback" not in response.text
