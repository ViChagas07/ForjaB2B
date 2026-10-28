"""Testes da porta LLMPort: timeout, 1 retry e erro tipado (Fase 12, passo 4).

Nenhum teste toca rede ou LLM real: o "LLM" e um stub local com script.
"""

import asyncio
from typing import cast

import pytest
from pydantic import BaseModel

from app.modules.ai.application.errors import LLMUnavailableError
from app.modules.ai.application.ports import LLMMessage, LLMPort, ResilientLLM


class _EchoSchema(BaseModel):
    answer: str


class _ScriptedLLM:
    """Stub de LLMPort com script por chamada (strings, erros ou sleeps)."""

    def __init__(self, script: list[object]) -> None:
        self._script = list(script)
        self.calls = 0

    async def complete_structured(
        self, *, schema: type[_EchoSchema], messages: list[LLMMessage]
    ) -> _EchoSchema:
        return cast("_EchoSchema", await self._next(schema=schema))

    async def complete_text(self, *, messages: list[LLMMessage]) -> str:
        return cast("str", await self._next(schema=str))

    async def _next(self, *, schema: object) -> object:
        self.calls += 1
        outcome = self._script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, float):
            await asyncio.sleep(outcome)  # simula lentidao (> timeout)
            return "late"
        return outcome


_TIMEOUT_S = 0.2


def _resilient(script: list[object]) -> tuple[ResilientLLM, _ScriptedLLM]:
    inner = _ScriptedLLM(script)
    return ResilientLLM(cast("LLMPort", inner), timeout_seconds=_TIMEOUT_S), inner


_MESSAGES: list[LLMMessage] = [{"role": "user", "content": "oi"}]


async def test_complete_text_sucesso_na_primeira_tentativa() -> None:
    resilient, inner = _resilient(["ok"])
    assert await resilient.complete_text(messages=_MESSAGES) == "ok"
    assert inner.calls == 1


async def test_complete_text_falha_transitoria_retenta_e_sucedede() -> None:
    resilient, inner = _resilient([LLMUnavailableError("boom"), "ok"])
    assert await resilient.complete_text(messages=_MESSAGES) == "ok"
    assert inner.calls == 2  # 1 tentativa + 1 retry


async def test_complete_text_esgota_retry_e_leva_erro_tipado() -> None:
    resilient, inner = _resilient([LLMUnavailableError("boom1"), LLMUnavailableError("boom2")])
    with pytest.raises(LLMUnavailableError):
        await resilient.complete_text(messages=_MESSAGES)
    assert inner.calls == 2  # exatamente 1 retry, nunca mais


async def test_timeout_dispara_retry_e_erro_tipado() -> None:
    resilient, inner = _resilient([_TIMEOUT_S * 5, _TIMEOUT_S * 5])
    with pytest.raises(LLMUnavailableError):
        await resilient.complete_text(messages=_MESSAGES)
    assert inner.calls == 2


async def test_excecao_inesperada_nao_e_retentada() -> None:
    resilient, inner = _resilient([ValueError("bug interno")])
    with pytest.raises(LLMUnavailableError):
        await resilient.complete_text(messages=_MESSAGES)
    assert inner.calls == 1  # falha nao-transitoria: sem retry


async def test_complete_structured_devolve_instancia_validada() -> None:
    resilient, _inner = _resilient([_EchoSchema(answer="oi")])
    out = await resilient.complete_structured(schema=_EchoSchema, messages=_MESSAGES)
    assert isinstance(out, _EchoSchema)
    assert out.answer == "oi"
