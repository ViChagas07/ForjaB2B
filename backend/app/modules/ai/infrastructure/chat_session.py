"""Store Redis do estado curto de follow-up (TTL + tamanho maximo).

O payload e sempre JSON escrito pelo servidor (`ChatSessionState`); este
adaptador apenas persiste. Falha de Redis nao derruba o chat: o follow-up
simplesmente nao encontra estado e o roteador normal assume.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.modules.ai.application.chat_session import ChatSessionState

_logger = get_logger(__name__)


class RedisChatSessionStore:
    def __init__(
        self,
        *,
        redis_client: Any,
        ttl_seconds: int = 1800,
        max_chars: int = 2000,
        key_prefix: str = "ai:chat:session:",
    ) -> None:
        self._redis = redis_client
        self._ttl = max(60, ttl_seconds)
        self._max_chars = max(500, max_chars)
        self._prefix = key_prefix

    async def load(self, conversation_id: uuid.UUID) -> ChatSessionState | None:
        try:
            raw = await self._redis.get(self._key(conversation_id))
        except Exception:  # noqa: BLE001 - cache nunca derruba o chat
            _logger.warning("chat_session_load_failed")
            return None
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str):
            return None
        return ChatSessionState.from_json(raw)

    async def save(self, conversation_id: uuid.UUID, state: ChatSessionState) -> None:
        payload = state.to_json()
        if len(payload) > self._max_chars:
            _logger.warning("chat_session_too_large", size=len(payload), max_chars=self._max_chars)
            return
        try:
            await self._redis.set(self._key(conversation_id), payload, ex=self._ttl)
        except Exception:  # noqa: BLE001 - cache nunca derruba o chat
            _logger.warning("chat_session_save_failed")

    def _key(self, conversation_id: uuid.UUID) -> str:
        return f"{self._prefix}{conversation_id}"
