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
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
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


# ---------------------------------------------------------------------------
# Chat (FASE 5): persistencia de conversas/mensagens.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ChatTurn:
    """Mensagem JA sanitizada/aprovada (unico conteudo que entra na memoria)."""

    role: str  # "user" | "assistant"
    content: str
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class ConversationView:
    """Conversa de chat (visitante = company_id/user_id None)."""

    id: uuid.UUID
    company_id: uuid.UUID | None
    user_id: uuid.UUID | None
    locale: str
    expires_at: datetime


class ConversationRepositoryPort(Protocol):
    """Persistencia de conversas. Escopo SEMPRE validado no servidor.

    `company_id`/`user_id` nulos = VISITANTE: so enxerga conversas sem dono
    (capacidade = conhecer o UUID). Logado: so conversas da MESMA empresa e do
    MESMO usuario. Tentativas fora do escopo sao tratadas como inexistentes
    (sem vazamento) ou levantam `ConversationAccessError` na escrita.
    """

    async def create(
        self,
        *,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        locale: str,
        expires_at: datetime,
    ) -> uuid.UUID:
        """Cria a conversa e devolve o UUID (nao adivinhavel)."""
        ...

    async def get(
        self,
        conversation_id: uuid.UUID,
        *,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> ConversationView | None:
        """Le a conversa dentro do escopo do chamador; None = fora do escopo."""
        ...

    async def append_message(
        self,
        conversation_id: uuid.UUID,
        *,
        role: str,
        content: str,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        """Grava UMA mensagem ja sanitizada/aprovada no escopo do chamador."""
        ...

    async def last_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> list[ChatTurn]:
        """Ultimas `limit` mensagens (ordem cronologica), no escopo do chamador."""
        ...

    async def touch(
        self,
        conversation_id: uuid.UUID,
        *,
        expires_at: datetime,
        company_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        """Renova last_message_at/expires_at (TTL) no escopo do chamador."""
        ...

    async def delete_expired(self, *, limit: int) -> int:
        """Limpeza TTL cross-tenant (funcao SECURITY DEFINER); devolve removidas."""
        ...
