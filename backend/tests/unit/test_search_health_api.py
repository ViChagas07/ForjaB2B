"""Testes do endpoint /health/search (sem Docker e sem banco/redis reais)."""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app
from app.modules.search.application.ports import SearchEngineHealth, SearchEngineState


class _FakeEngine:
    """Motor de busca falso, sem rede, para exercitar cada estado."""

    def __init__(self, health: SearchEngineHealth) -> None:
        self._health = health

    async def check_health(self) -> SearchEngineHealth:
        return self._health

    async def close(self) -> None:
        return None


def _app(*, enabled: bool, url: str = "http://localhost:9200", max_retries: int = 3) -> FastAPI:
    return create_app(
        Settings(
            otel_enabled=False,
            log_format="console",
            elasticsearch_enabled=enabled,
            elasticsearch_url=url,
            elasticsearch_max_retries=max_retries,
            elasticsearch_request_timeout_seconds=1.0,
        )
    )


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_health_search_desabilitado() -> None:
    response = await _get(_app(enabled=False), "/health/search")
    assert response.status_code == 200
    assert response.json() == {"status": "disabled", "detail": None}


async def test_health_search_ok() -> None:
    app = _app(enabled=False)
    app.state.search_engine = _FakeEngine(
        SearchEngineHealth(state=SearchEngineState.OK, detail="green")
    )
    response = await _get(app, "/health/search")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "detail": "green"}


async def test_health_search_degradado() -> None:
    app = _app(enabled=False)
    app.state.search_engine = _FakeEngine(SearchEngineHealth(state=SearchEngineState.DEGRADED))
    response = await _get(app, "/health/search")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


async def test_health_search_indisponivel_com_servidor_fora() -> None:
    app = _app(enabled=True, url="http://127.0.0.1:9", max_retries=0)
    try:
        response = await _get(app, "/health/search")
    finally:
        await app.state.search_engine.close()
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


async def test_aplicacao_inicia_com_elasticsearch_fora() -> None:
    """Startup nunca e fatal: a app sobe com o Elasticsearch fora do ar."""
    app = _app(enabled=True, url="http://127.0.0.1:9", max_retries=0)
    try:
        assert app.state.search_engine is not None
    finally:
        await app.state.search_engine.close()
