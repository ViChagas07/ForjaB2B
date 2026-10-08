"""Testes de integracao: engine, session factory e ciclo de vida transacional.

PostgreSQL real via Testcontainers com o bootstrap do projeto. A engine usa
a role de runtime (forja_app), como a aplicacao em producao.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


async def test_engine_conecta_com_role_de_runtime(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        row = (await connection.execute(text("SELECT current_user"))).scalar_one()
        assert row == "forja_app"


async def test_session_executa_e_faz_commit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await session.begin()
        assert session.in_transaction()
        value = (await session.execute(text("SELECT 1"))).scalar_one()
        await session.commit()
        assert value == 1
        assert not session.in_transaction()


async def test_session_rollback_descarta_transacao(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await session.begin()
        await session.execute(text("SELECT 1"))
        assert session.in_transaction()
        await session.rollback()
        assert not session.in_transaction()

        # Nova transacao na mesma sessao continua funcional apos rollback.
        value = (await session.execute(text("SELECT 2"))).scalar_one()
        assert value == 2
        await session.commit()
