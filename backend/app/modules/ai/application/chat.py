"""Servico do assistente de chat (FASE 5c): abre/retoma conversa e executa o grafo.

A conversa e resolvida SEMPRE no servidor (ConversationService da FASE 5a):
visitante so reabre conversa sem dono (posse do UUID); logado so a da mesma
empresa E usuario; caso contrario => None (endpoint responde 404 neutro).
O historico enviado ao grafo e truncado em AI_CHAT_HISTORY_TURNS e so contem
mensagens aprovadas; a gravacao (user sanitizado + assistant aprovado) acontece
no no `persist` do grafo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.ai.application.chat_graph import ChatGraph
from app.modules.ai.application.conversation_service import (
    ConversationScope,
    ConversationService,
)
from app.modules.ai.application.product_cards import ProductCard


@dataclass(frozen=True, kw_only=True)
class ChatResult:
    conversation_id: uuid.UUID
    reply: str
    product_cards: list[ProductCard]


class ChatService:
    def __init__(
        self,
        *,
        conversations: ConversationService,
        graph: ChatGraph,
    ) -> None:
        self._conversations = conversations
        self._graph = graph

    async def handle(
        self,
        *,
        conversation_id: uuid.UUID | None,
        scope: ConversationScope,
        locale: str,
        message: str,
        auth: Any,
    ) -> ChatResult | None:
        conversation = await self._conversations.open_or_resume(
            conversation_id=conversation_id, scope=scope, locale=locale
        )
        if conversation is None:
            return None
        history = await self._conversations.last_turns(conversation)
        outcome = await self._graph.run(
            conversation=conversation,
            locale=locale,
            message=message,
            history=history,
            auth=auth,
        )
        return ChatResult(
            conversation_id=conversation.id,
            reply=outcome.reply,
            product_cards=outcome.cards,
        )
