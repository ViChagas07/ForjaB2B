"""Testes de CORS: origens explicitas, preflight e credenciais.

Nao usam banco nem Redis: exercitam a app factory e o CORSMiddleware, que
responde ao preflight antes de qualquer rota de negocio.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app

_ALLOWED = "http://localhost:3010"
_DISALLOWED = "https://evil.example"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "otel_enabled": False,
        "cors_origins": f"http://localhost:3000,{_ALLOWED}",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture()
async def cors_client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_preflight_origem_permitida_retorna_cabecalhos(
    cors_client: httpx.AsyncClient,
) -> None:
    response = await cors_client.options(
        "/api/v1/catalog/products",
        headers={
            "Origin": _ALLOWED,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,accept-language",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == _ALLOWED
    assert response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["access-control-max-age"] == "600"
    assert "access-control-allow-credentials" not in response.headers


async def test_preflight_origem_nao_permitida_nao_retorna_cors(
    cors_client: httpx.AsyncClient,
) -> None:
    response = await cors_client.options(
        "/api/v1/catalog/products",
        headers={"Origin": _DISALLOWED, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 400
    # Sem Access-Control-Allow-Origin o navegador bloqueia a resposta; o
    # Starlette ainda ecoa allow-methods no corpo do 400, o que nao autoriza.
    assert "access-control-allow-origin" not in response.headers


async def test_requisicao_com_credenciais_nao_usa_curinga() -> None:
    app = create_app(_settings(cors_allow_credentials=True))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/health/live", headers={"Origin": _ALLOWED, "Cookie": "session=abc"}
            )
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)

    assert response.headers["access-control-allow-origin"] == _ALLOWED
    assert response.headers["access-control-allow-origin"] != "*"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_config_rejeita_curinga() -> None:
    with pytest.raises(ValidationError):
        _settings(cors_origins="*")

    with pytest.raises(ValidationError):
        _settings(cors_origins="http://localhost:3000,https://evil.example/path")


def test_config_rejeita_lista_vazia() -> None:
    with pytest.raises(ValidationError):
        _settings(cors_origins="  ,  ")
