"""Armazenamento de state anti-CSRF do OAuth no Redis (single-use, TTL).

O state e gerado pelo backend, gravado com TTL curto e consumido uma unica vez
no callback. ``GETDEL`` torna a validacao atomica: reuso (CSRF) devolve False.
"""

from __future__ import annotations

import redis.asyncio as redis

_KEY_PREFIX = "oauth_state:"


class RedisOAuthStateStore:
    """Implementacao da porta OAuthStateStore sobre Redis."""

    def __init__(self, client: redis.Redis[str]) -> None:
        self._client = client

    async def put(self, state: str, ttl_seconds: int) -> None:
        await self._client.set(f"{_KEY_PREFIX}{state}", "1", ex=ttl_seconds)

    async def consume(self, state: str) -> bool:
        return await self._client.getdel(f"{_KEY_PREFIX}{state}") is not None
