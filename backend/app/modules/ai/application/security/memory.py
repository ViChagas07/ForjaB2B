"""Memoria de conversa a prova de envenenamento (item E.10).

Regras estruturais da superficie:
- so entram na memoria mensagens do usuario JA SANITIZADAS (aprovadas pelo
  gate de entrada) e respostas FINAIS do assistente JA APROVADAS pelo
  output guard — os unicos metodos expostos sao `remember_user` e
  `remember_assistant`; saida de ferramenta, texto de produto e system
  prompt NAO tem caminho de entrada;
- reinjecao: janela das ultimas `max_turns` mensagens, entregue como DADO
  nao confiavel (o PromptBuilder encapsula no bloco delimitado);
- SEM resumo gerado por LLM persistido (evita envenenamento por resumo);
- memoria isolada por conversation_id (nunca entre usuarios/empresas),
  com TTL renovado a cada atividade.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.modules.ai.domain.security.normalize import normalize_user_text


@dataclass(frozen=True, kw_only=True)
class MemoryTurn:
    """Uma mensagem ja aprovada para memoria (so user sanitizado/assistant ok)."""

    role: str  # "user" | "assistant"
    content: str
    at: datetime


class ConversationMemoryStore(Protocol):
    """Store de memoria (in-memory para testes; Redis/TTL na FASE 3)."""

    def load(self, conversation_id: str) -> tuple[MemoryTurn, ...]: ...

    def save(self, conversation_id: str, turns: tuple[MemoryTurn, ...]) -> None: ...


class InMemoryConversationMemoryStore:
    """Store em memoria com TTL por conversa (renovado a cada escrita)."""

    def __init__(self, *, ttl_days: int, clock: Callable[[], datetime]) -> None:
        self._ttl = timedelta(days=ttl_days)
        self._clock = clock
        self._conversations: dict[str, tuple[MemoryTurn, ...]] = {}

    def load(self, conversation_id: str) -> tuple[MemoryTurn, ...]:
        turns = self._conversations.get(conversation_id, ())
        if not turns:
            return ()
        newest = max(turn.at for turn in turns)
        if self._clock() - newest > self._ttl:
            del self._conversations[conversation_id]
            return ()
        return turns

    def save(self, conversation_id: str, turns: tuple[MemoryTurn, ...]) -> None:
        if not turns:
            self._conversations.pop(conversation_id, None)
            return
        self._conversations[conversation_id] = turns


class SanitizedConversationMemory:
    """Politica de memoria: so conteudo aprovado, janela curta, isolada."""

    def __init__(self, store: ConversationMemoryStore, *, max_turns: int) -> None:
        self._store = store
        self._max_turns = max_turns

    def remember_user(
        self,
        conversation_id: str,
        *,
        sanitized_text: str,
        now: datetime | None = None,
    ) -> None:
        self._append(
            conversation_id,
            MemoryTurn(role="user", content=self._sanitized(sanitized_text), at=now or _now()),
        )

    def remember_assistant(
        self,
        conversation_id: str,
        *,
        approved_text: str,
        now: datetime | None = None,
    ) -> None:
        self._append(
            conversation_id,
            MemoryTurn(role="assistant", content=approved_text, at=now or _now()),
        )

    def window(self, conversation_id: str) -> tuple[tuple[str, str], ...]:
        """Ultimas `max_turns` mensagens aprovadas (reinjecao como dado)."""
        turns = self._store.load(conversation_id)
        recent = turns[-self._max_turns :]
        return tuple((turn.role, turn.content) for turn in recent)

    def _sanitized(self, text: str, max_chars: int = 500) -> str:
        # Defesa extra: a memoria JAMAIS guarda o bruto; re-normaliza.
        return normalize_user_text(text, max_chars=max_chars).text

    def _append(self, conversation_id: str, turn: MemoryTurn) -> None:
        turns = self._store.load(conversation_id)
        self._store.save(conversation_id, (*turns, turn))


def _now() -> datetime:
    return datetime.now(UTC)
