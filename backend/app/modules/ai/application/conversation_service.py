"""Servico de conversas do chat (FASE 5a).

Superficie ESTRUTURALMENTE limitada (nunca ha `append` generico):
- `append_user_message`: recebe SOMENTE texto ja sanitizado pelo gate da Fase 2
  e re-normaliza (NFKC/limite) antes de gravar;
- `append_assistant_message`: recebe SOMENTE a resposta final ja aprovada pelo
  output guard da Fase 2.
Nunca existe caminho para gravar saida de ferramenta, texto de produto ou
system prompt (sem metodo para isso). Escopo SEMPRE validado no servidor:
visitante so reabre conversa sem dono (posse do UUID); usuario logado so
reabre a conversa da propria empresa E do proprio usuario. TTL renovado a cada
mensagem (`AI_CONVERSATION_TTL_DAYS`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.modules.ai.application.ports import (
    ChatTurn,
    ConversationRepositoryPort,
    ConversationView,
)
from app.modules.ai.domain.security.normalize import normalize_user_text

DEFAULT_MAX_MESSAGE_CHARS = 500


@dataclass(frozen=True, kw_only=True)
class ConversationScope:
    """Escopo do chamador (vindo do JWT/servidor; nunca do corpo)."""

    company_id: uuid.UUID | None
    user_id: uuid.UUID | None

    @property
    def is_visitor(self) -> bool:
        return self.company_id is None and self.user_id is None


class ConversationService:
    """Abre/retoma conversas e grava apenas memoria aprovada, com TTL."""

    def __init__(
        self,
        *,
        repository: ConversationRepositoryPort,
        ttl_days: int,
        history_turns: int,
        max_message_chars: int = DEFAULT_MAX_MESSAGE_CHARS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._ttl_days = ttl_days
        self._history_turns = history_turns
        self._max_message_chars = max_message_chars
        self._now = now or (lambda: datetime.now(UTC))

    async def open_or_resume(
        self,
        *,
        conversation_id: uuid.UUID | None,
        scope: ConversationScope,
        locale: str,
    ) -> ConversationView | None:
        """Retoma a conversa se o chamador for o dono; None = inexistente/negado."""
        if conversation_id is None:
            return await self._create(scope=scope, locale=locale)
        view = await self._repository.get(
            conversation_id, company_id=scope.company_id, user_id=scope.user_id
        )
        if view is None or not _authorized(view, scope):
            return None
        return view

    async def last_turns(self, conversation: ConversationView) -> list[ChatTurn]:
        """Ultimas AI_CHAT_HISTORY_TURNS mensagens (user/assistant aprovadas)."""
        return await self._repository.last_messages(
            conversation.id,
            limit=self._history_turns,
            company_id=conversation.company_id,
            user_id=conversation.user_id,
        )

    async def append_user_message(
        self, conversation: ConversationView, *, sanitized_text: str
    ) -> None:
        """Grava a mensagem do usuario (ja sanitizada) — re-normaliza por defesa."""
        text = normalize_user_text(sanitized_text, max_chars=self._max_message_chars).text
        if not text:
            return
        await self._append(conversation, role="user", content=text)

    async def append_assistant_message(
        self, conversation: ConversationView, *, approved_text: str
    ) -> None:
        """Grava a resposta final (ja aprovada pelo output guard da Fase 2)."""
        text = approved_text.strip()
        if not text:
            return
        await self._append(conversation, role="assistant", content=text)

    async def _append(self, conversation: ConversationView, *, role: str, content: str) -> None:
        await self._repository.append_message(
            conversation.id,
            role=role,
            content=content,
            company_id=conversation.company_id,
            user_id=conversation.user_id,
        )
        await self._repository.touch(
            conversation.id,
            expires_at=self._expires_at(),
            company_id=conversation.company_id,
            user_id=conversation.user_id,
        )

    async def _create(self, *, scope: ConversationScope, locale: str) -> ConversationView:
        expires_at = self._expires_at()
        conversation_id = await self._repository.create(
            company_id=scope.company_id,
            user_id=scope.user_id,
            locale=locale,
            expires_at=expires_at,
        )
        return ConversationView(
            id=conversation_id,
            company_id=scope.company_id,
            user_id=scope.user_id,
            locale=locale,
            expires_at=expires_at,
        )

    def _expires_at(self) -> datetime:
        return self._now() + timedelta(days=self._ttl_days)


def _authorized(view: ConversationView, scope: ConversationScope) -> bool:
    """Dono exato: visitante (sem dono) x logado (mesma empresa E usuario)."""
    if scope.is_visitor:
        return view.company_id is None and view.user_id is None
    return (
        scope.company_id is not None
        and scope.user_id is not None
        and view.company_id == scope.company_id
        and view.user_id == scope.user_id
    )
