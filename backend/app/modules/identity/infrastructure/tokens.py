"""Armazenamento de refresh tokens no Redis (rotacao/revogacao).

Refresh tokens sao opacos, de alta entropia, e vivem como dados temporarios no
Redis com TTL (a fonte de verdade continua sendo o PostgreSQL; o Redis nao
guarda estado financeiro nem identidade permanente). Cada login emite um token
novo; refresh consome e rotaciona; logout revoga.
"""

from __future__ import annotations

import json
import uuid

import redis.asyncio as redis

from app.modules.identity.application.ports import RefreshTokenPayload

_KEY_PREFIX = "refresh:"


class RedisRefreshTokenStore:
    """Implementacao da porta RefreshTokenStore sobre Redis."""

    def __init__(self, client: redis.Redis[str]) -> None:
        self._client = client

    async def put(
        self, refresh_token_id: str, payload: RefreshTokenPayload, ttl_seconds: int
    ) -> None:
        data = {
            "user_id": str(payload.user_id),
            "company_id": str(payload.company_id),
            "role": payload.role,
        }
        await self._client.set(f"{_KEY_PREFIX}{refresh_token_id}", json.dumps(data), ex=ttl_seconds)

    async def get(self, refresh_token_id: str) -> RefreshTokenPayload | None:
        raw = await self._client.get(f"{_KEY_PREFIX}{refresh_token_id}")
        if raw is None:
            return None
        data = json.loads(raw)
        return RefreshTokenPayload(
            user_id=uuid.UUID(data["user_id"]),
            company_id=uuid.UUID(data["company_id"]),
            role=data["role"],
        )

    async def delete(self, refresh_token_id: str) -> None:
        await self._client.delete(f"{_KEY_PREFIX}{refresh_token_id}")
