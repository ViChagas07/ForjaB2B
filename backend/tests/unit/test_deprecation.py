"""Rotas depreciadas: cabecalhos, metrica e `deprecated: true` no OpenAPI."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.interface.deprecation import DeprecationInfo
from app.main import create_app


def test_headers_de_depreciacao_rfc() -> None:
    info = DeprecationInfo(
        sunset=date(2027, 4, 30),
        successor="/api/v1/payments/stripe/webhook",
        reason="Legado",
    )
    headers = info.headers()

    assert headers["Deprecation"] == "true"
    assert headers["Sunset"] == "Fri, 30 Apr 2027 00:00:00 GMT"
    assert headers["Link"] == '</api/v1/payments/stripe/webhook>; rel="successor-version"'
    assert headers["Warning"].startswith("299")


@pytest.fixture()
async def client() -> httpx.AsyncClient:
    app = create_app(Settings(environment="test", otel_enabled=False, elasticsearch_enabled=False))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def test_rota_depreciada_devolve_cabecalhos(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/payments/webhook",
        content=b"{}",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 401
    assert response.headers["deprecation"] == "true"
    assert response.headers["sunset"] == "Fri, 30 Apr 2027 00:00:00 GMT"
    assert response.headers["link"].endswith('rel="successor-version"')
    assert response.headers["warning"].startswith("299")


async def test_rota_nao_depreciada_nao_recebe_cabecalhos(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert "deprecation" not in response.headers
    assert "sunset" not in response.headers


async def test_schema_marca_rota_como_depreciada(client: httpx.AsyncClient) -> None:
    transport = cast(Any, client._transport)
    schema = transport.app.openapi()

    operation = schema["paths"]["/api/v1/payments/webhook"]["post"]
    assert operation["deprecated"] is True

    order = schema["paths"]["/api/v1/orders"]["post"]
    assert "deprecated" not in order
