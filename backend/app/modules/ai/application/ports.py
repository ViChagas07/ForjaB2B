"""Porta LLMPort e politica de resiliencia (timeout + 1 retry).

O adaptador concreto (langchain-openai) vive na infrastructure; aqui fica o
contrato e o envelope transversal:

- `complete_structured(schema, messages)`: saida estruturada ja validada no
  schema Pydantic informado (o chamador recebe uma instancia de `schema`).
- `complete_text(messages)`: saida textual curta (ex.: mensagem do chat).
- `ResilientLLM`: aplica `LLM_TIMEOUT_S` por tentativa e UMA repeticao
  (total de 2 tentativas) quando a falha e transitoria (timeout ou
  `LLMUnavailableError` do adaptador). Excecao inesperada nao e retentada —
  vira `LLMUnavailableError` imediatamente. Mensagens de erro nunca carregam
  conteudo de prompt/resposta nem chaves.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, TypedDict, TypeVar, runtime_checkable

from pydantic import BaseModel

from app.modules.ai.application.errors import LLMUnavailableError

_MAX_ATTEMPTS = 2  # 1 tentativa + 1 retry


class LLMMessage(TypedDict):
    """Mensagem de conversa (texto simples, sem HTML, sem PII)."""

    role: str  # "system" | "user" | "assistant" (contrato com o adaptador)
    content: str


TModel = TypeVar("TModel", bound=BaseModel)
TReturn = TypeVar("TReturn")


@runtime_checkable
class LLMPort(Protocol):
    """Porta de acesso a um LLM compativel com API OpenAI (ou fake de teste)."""

    async def complete_structured(
        self, *, schema: type[TModel], messages: Sequence[LLMMessage]
    ) -> TModel: ...

    async def complete_text(self, *, messages: Sequence[LLMMessage]) -> str: ...


class ResilientLLM:
    """Envelope `LLMPort`: timeout por tentativa + 1 retry, erro tipado.

    Somente falhas transitorias (timeout / `LLMUnavailableError`) sao
    retentadas. Qualquer outra excecao e convertida em `LLMUnavailableError`
    sem retry (falha nao-transitoria; retentar e inutil e atrasa o fallback).
    """

    def __init__(self, inner: LLMPort, *, timeout_seconds: float) -> None:
        self._inner = inner
        self._timeout_seconds = timeout_seconds

    async def complete_structured(
        self, *, schema: type[TModel], messages: Sequence[LLMMessage]
    ) -> TModel:
        return await self._call_with_resilience(
            lambda: self._inner.complete_structured(schema=schema, messages=messages)
        )

    async def complete_text(self, *, messages: Sequence[LLMMessage]) -> str:
        return await self._call_with_resilience(
            lambda: self._inner.complete_text(messages=messages)
        )

    async def _call_with_resilience(self, call: Callable[[], Awaitable[TReturn]]) -> TReturn:
        last_error: BaseException | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return await asyncio.wait_for(call(), timeout=self._timeout_seconds)
            except (TimeoutError, LLMUnavailableError) as exc:
                # Transitoria: timeout da tentativa ou indisponibilidade
                # reportada pelo adaptador. Retenta ate esgotar.
                last_error = exc
                if attempt < _MAX_ATTEMPTS:
                    continue
            except Exception as exc:
                # Nao-transitoria (ex.: saida invalida): converte sem retry.
                raise LLMUnavailableError("llm_failed") from exc
        raise LLMUnavailableError("llm_unavailable_after_retries") from last_error
