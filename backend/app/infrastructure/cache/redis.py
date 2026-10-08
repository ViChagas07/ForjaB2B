"""Cliente Redis assincrono da fundacao.

Na Fase 0 o Redis entra apenas como dependencia de infraestrutura (readiness
e base para cache/rate-limit futuros). Nenhuma logica de negocio aqui.
"""

from __future__ import annotations

from typing import Protocol, cast

import redis.asyncio as redis

from app.core.config import Settings

_DEFAULT_SOCKET_TIMEOUT_SECONDS = 2.0


def create_redis_client(settings: Settings) -> redis.Redis[str]:
    """Cliente Redis com timeouts curtos e explicitos (nao conecta na criacao)."""
    return redis.from_url(
        str(settings.redis_url),
        socket_connect_timeout=_DEFAULT_SOCKET_TIMEOUT_SECONDS,
        socket_timeout=_DEFAULT_SOCKET_TIMEOUT_SECONDS,
        decode_responses=True,
    )


class _AsyncCloseable(Protocol):
    """Vista estrutural do shutdown assincrono do cliente Redis.

    redis-py 8.1 expoe `aclose()` em runtime (redis/asyncio/client.py), mas o
    mypy nao resolve o atributo na classe generica Redis. O cast estrutural
    documenta o contrato real sem supressao de tipagem e sem Any.
    """

    async def aclose(self, close_connection_pool: bool | None = None) -> None: ...


async def close_redis_client(client: redis.Redis[str]) -> None:
    await cast(_AsyncCloseable, client).aclose()
