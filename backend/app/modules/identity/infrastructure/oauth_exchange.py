"""Armazenamento de exchange codes OAuth no Redis (single-use, curta duracao).

O exchange code e gerado pelo backend apos o callback, guardado no servidor com
TTL curto e consumido atomicamente uma unica vez (``GETDEL``). Nenhum token ou
identidade trafega na URL de redirect; apenas o codigo opaco.
"""

from __future__ import annotations

import json

import redis.asyncio as redis

from app.modules.identity.application.ports import OAuthExchange

_KEY_PREFIX = "oauth_exchange:"


class RedisOAuthExchangeCodeStore:
    """Implementacao da porta OAuthExchangeCodeStore sobre Redis."""

    def __init__(self, client: redis.Redis[str]) -> None:
        self._client = client

    async def put(self, code: str, payload: OAuthExchange, ttl_seconds: int) -> None:
        data = {
            "status": payload.status,
            "access_token": payload.access_token,
            "refresh_token": payload.refresh_token,
            "token_type": payload.token_type,
            "expires_in": payload.expires_in,
            "user_id": payload.user_id,
            "email": payload.email,
            "full_name": payload.full_name,
            "role": payload.role,
        }
        await self._client.set(f"{_KEY_PREFIX}{code}", json.dumps(data), ex=ttl_seconds)

    async def consume(self, code: str) -> OAuthExchange | None:
        raw = await self._client.getdel(f"{_KEY_PREFIX}{code}")
        if raw is None:
            return None
        data = json.loads(raw)
        return OAuthExchange(
            status=data["status"],
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type"),
            expires_in=data.get("expires_in"),
            user_id=data.get("user_id"),
            email=data.get("email"),
            full_name=data.get("full_name"),
            role=data.get("role"),
        )
