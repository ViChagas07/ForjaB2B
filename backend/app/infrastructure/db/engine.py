"""Engine assincrona do SQLAlchemy 2.x configurada a partir de Settings.

Pool com `pool_reset_on_return="rollback"`: ao devolver a conexao ao pool,
qualquer estado transacional residual e descartado. Combinado ao fato de as
GUCs de tenant serem definidas com escopo de transacao (set_config is_local),
nao ha estado de tenant persistente na conexao para vazar entre requests.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Cria a engine assincrona (asyncpg) com pool explicito.

    Nenhuma conexao e aberta na criacao; o primeiro acesso ocorre no uso.
    """
    return create_async_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
