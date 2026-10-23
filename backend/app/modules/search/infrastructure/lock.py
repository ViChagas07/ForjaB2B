"""Advisory lock do PostgreSQL para exclusao mutua da reconciliacao.

O lock e de sessao (nao de transacao) e fica preso a uma conexao dedicada
durante toda a reconciliacao. Se o processo morrer, a conexao fecha e o
PostgreSQL libera o lock automaticamente. Duas instancias que tentem reconciliar
ao mesmo tempo: a segunda recebe ``False`` e deve sair sem tocar no indice.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

RECONCILE_LOCK_KEY = "forja:search:reconcile"

_TRY_LOCK = text("SELECT pg_try_advisory_lock(hashtext(:key))")
_UNLOCK = text("SELECT pg_advisory_unlock(hashtext(:key))")


class PostgresAdvisoryLock:
    """Lock consultivo nomeado, mantido por uma conexao dedicada."""

    def __init__(self, engine: AsyncEngine, *, key: str = RECONCILE_LOCK_KEY) -> None:
        self._engine = engine
        self._key = key
        self._connection: AsyncConnection | None = None

    async def try_acquire(self) -> bool:
        """Tenta adquirir o lock; em caso de falha, a conexao e devolvida ao pool."""
        connection = await self._engine.connect()
        acquired = bool((await connection.execute(_TRY_LOCK, {"key": self._key})).scalar())
        if not acquired:
            await connection.close()
            return False
        self._connection = connection
        return True

    async def release(self) -> None:
        connection = self._connection
        if connection is None:
            return
        self._connection = None
        try:
            await connection.execute(_UNLOCK, {"key": self._key})
        finally:
            await connection.close()
