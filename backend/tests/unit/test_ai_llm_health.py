"""Testes do GET /health/llm e do probe cacheado (sem LM Studio/rede)."""

from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from app.interface.health import router
from app.modules.ai.infrastructure.llm_health import LLMHealthProbe

MODEL = "qwen/qwen3.5-9b"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_probe(fetch, *, clock: Clock, enabled: bool = True) -> LLMHealthProbe:
    return LLMHealthProbe(
        enabled=enabled,
        base_url="http://lm-studio.test/v1",
        model=MODEL,
        timeout_seconds=1.0,
        cache_seconds=30.0,
        clock=clock,
        fetch_model_ids=fetch,
    )


async def test_probe_disponivel_quando_modelo_esta_carregado() -> None:
    calls = 0

    async def fetch() -> set[str]:
        nonlocal calls
        calls += 1
        return {MODEL}

    result = await make_probe(fetch, clock=Clock()).check()
    assert result.available is True
    assert result.enabled is True
    assert result.model == MODEL
    assert calls == 1


async def test_probe_cacheia_por_30s() -> None:
    calls = 0

    async def fetch() -> set[str]:
        nonlocal calls
        calls += 1
        return {MODEL}

    clock = Clock()
    probe = make_probe(fetch, clock=clock)
    await probe.check()
    await probe.check()
    assert calls == 1
    clock.now += 31
    await probe.check()
    assert calls == 2


async def test_probe_falha_vira_indisponivel_sem_excecao() -> None:
    async def fetch() -> set[str]:
        raise httpx.ConnectError("offline")

    result = await make_probe(fetch, clock=Clock()).check()
    assert result.available is False
    assert result.enabled is True


async def test_probe_desligado_nao_chama_fetch() -> None:
    async def fetch() -> set[str]:
        raise AssertionError("nao deveria chamar")

    result = await make_probe(fetch, clock=Clock(), enabled=False).check()
    assert result.available is False
    assert result.enabled is False


async def test_rota_health_llm_sempre_200() -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.settings = SimpleNamespace(llm_model=MODEL)
    app.state.llm_health_probe = make_probe(_models_offline, clock=Clock())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/llm")
    assert response.status_code == 200
    assert response.json() == {"available": False, "enabled": True, "model": MODEL}


async def _models_offline() -> set[str]:
    raise httpx.ConnectError("offline")


async def test_health_llm_nao_afeta_health_principal() -> None:
    app = FastAPI()
    app.include_router(router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        llm = await client.get("/health/llm")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert llm.status_code == 200
    assert llm.json()["available"] is False
