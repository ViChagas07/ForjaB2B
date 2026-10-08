"""Session factory assincrona do SQLAlchemy 2.x."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Factory de AsyncSession.

    `expire_on_commit=False` evita IO implicito apos commit (fora de
    transacao), mantendo o ciclo de vida da transacao explicito.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
