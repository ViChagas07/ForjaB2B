"""Testes do endpoint publico /api/v1/fx/rates (sem rede externa)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.fx.application.errors import FxRatesUnavailableError
from app.modules.fx.application.get_rates import FxRatesView
from app.modules.fx.domain.rates import SUPPORTED_CURRENCIES, FxRates
from app.modules.fx.interface.schemas import FxRatesResponse

_FIXED_NOW = datetime(2026, 10, 30, 23, 0, tzinfo=UTC)
_RATES = {
    "BRL": "1",
    "USD": "0.18408",
    "EUR": "0.16477",
    "GBP": "0.13738",
    "CAD": "0.25713",
    "AUD": "0.26204",
    "JPY": "28.946",
    "CNY": "1.2246",
}


def _sample_rates() -> FxRates:
    return FxRates(
        rates={code: Decimal(value) for code, value in _RATES.items()},
        rate_date=date(2026, 10, 30),
        fetched_at=_FIXED_NOW,
        source="Frankfurter / European Central Bank",
    )


class _FakeUseCase:
    def __init__(self, result: FxRatesView | Exception) -> None:
        self.result = result

    async def run(self) -> FxRatesView:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@asynccontextmanager
async def _app_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app(Settings(environment="test", otel_enabled=False, rate_limit_enabled=False))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield app, client
    finally:
        await app.state.fx_rate_provider.aclose()
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


async def test_endpoint_retorna_as_oito_moedas_com_fonte_e_data() -> None:
    async with _app_client() as (app, client):
        app.state.fx_get_rates = _FakeUseCase(FxRatesView(rates=_sample_rates(), stale=False))

        response = await client.get("/api/v1/fx/rates")

    assert response.status_code == 200
    body = response.json()
    assert body["base"] == "BRL"
    assert set(body["rates"]) == set(SUPPORTED_CURRENCIES)
    assert body["rates"]["BRL"] == "1"
    assert body["rates"]["USD"] == "0.18408"
    assert body["rate_date"] == "2026-10-30"
    assert body["fetched_at"] == "2026-10-30T23:00:00Z"
    assert body["source"] == "Frankfurter / European Central Bank"
    assert body["stale"] is False
    assert "max-age=300" in response.headers["cache-control"]


async def test_endpoint_stale_reduz_o_cache_e_marca_a_resposta() -> None:
    async with _app_client() as (app, client):
        app.state.fx_get_rates = _FakeUseCase(FxRatesView(rates=_sample_rates(), stale=True))

        response = await client.get("/api/v1/fx/rates")

    assert response.status_code == 200
    assert response.json()["stale"] is True
    assert response.headers["cache-control"] == "public, max-age=60"


async def test_endpoint_sem_taxa_responde_503_problem_details_sem_stack() -> None:
    async with _app_client() as (app, client):
        app.state.fx_get_rates = _FakeUseCase(FxRatesUnavailableError())

        response = await client.get("/api/v1/fx/rates")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "urn:forja:problem:fx_rates_unavailable"
    assert body["status"] == 503
    assert "Traceback" not in body["detail"]


def test_schema_rejeita_moeda_fora_da_lista_fechada() -> None:
    base = {code: Decimal(value) for code, value in _RATES.items()}

    with pytest.raises(ValidationError):
        FxRatesResponse(
            base="BRL",
            rates={**base, "CHF": Decimal("0.15")},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
            stale=False,
        )

    with pytest.raises(ValidationError):
        FxRatesResponse(
            base="BRL",
            rates={key: value for key, value in base.items() if key != "USD"},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
            stale=False,
        )

    with pytest.raises(ValidationError):
        FxRatesResponse(
            base="BRL",
            rates={**base, "BRL": Decimal("2")},
            rate_date=date(2026, 10, 30),
            fetched_at=_FIXED_NOW,
            source="x",
            stale=False,
        )


async def test_openapi_documenta_rota_tag_e_erro_503() -> None:
    async with _app_client() as (app, _):
        schema = app.openapi()

    operation = schema["paths"]["/api/v1/fx/rates"]["get"]
    assert operation["tags"] == ["fx"]
    declared_tags = {tag["name"] for tag in schema["tags"]}
    assert "fx" in declared_tags
    assert (
        operation["responses"]["503"]["content"]["application/problem+json"]["schema"]["$ref"]
        == "#/components/schemas/ProblemDetails"
    )
