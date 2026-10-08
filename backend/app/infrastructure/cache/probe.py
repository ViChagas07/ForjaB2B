"""Probe de readiness do Redis."""

from __future__ import annotations

import redis.asyncio as redis


async def ping_redis(client: redis.Redis[str]) -> bool:
    """PING com timeout curto; falha de conexao devolve False."""
    try:
        return bool(await client.ping())
    except Exception:  # noqa: BLE001 - probe de readiness nao propaga
        return False
