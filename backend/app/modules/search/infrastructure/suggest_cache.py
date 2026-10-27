"""Cache curto (Redis) das respostas ANONIMAS do /search/suggest.

Somente leitura publica: respostas autenticadas resolvem preco por empresa e
NUNCA sao cacheadas (o middleware de security headers ja emite ``no-store``
para requisicoes com Authorization). Falha do Redis nunca derruba a rota:
``get``/``set`` degradam para "sem cache" com log de aviso.

A chave inclui a versao do indice (um reindex invalida o cache em massa), o
locale negociado e o termo normalizado (trim + lowercase), alinhado com a
chave de cache do frontend (``features/search/query-keys.ts``).
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.logging import get_logger

_logger = get_logger(__name__)

SUGGEST_CACHE_TTL_SECONDS = 30


class SuggestCache:
    """Leitura/escrita best-effort de payloads JSON do suggest no Redis."""

    def __init__(
        self,
        *,
        redis_client: Redis[str] | None,
        index_version: int,
        ttl_seconds: int = SUGGEST_CACHE_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._index_version = index_version
        self._ttl = ttl_seconds

    def key_for(self, *, q: str, locale: str) -> str:
        normalized = q.strip().lower()
        return f"search:suggest:v{self._index_version}:{locale}:{normalized}"

    async def get(self, *, key: str) -> str | None:
        """Payload JSON em cache (``None`` em miss ou falha de Redis)."""
        if self._redis is None:
            return None
        try:
            return await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001 - falha de Redis degrada sem cache
            _logger.warning("suggest_cache_read_failed", error=str(exc))
            return None

    async def set(self, *, key: str, payload: str) -> None:
        """Grava com TTL curto; falha de Redis e ignorada (best-effort)."""
        if self._redis is None:
            return
        try:
            await self._redis.set(key, payload, ex=self._ttl)
        except Exception as exc:  # noqa: BLE001 - falha de Redis degrada sem cache
            _logger.warning("suggest_cache_write_failed", error=str(exc))
