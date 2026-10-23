"""Exclusao mutua da reconciliacao via advisory lock do PostgreSQL."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.search.infrastructure.lock import PostgresAdvisoryLock


async def test_segunda_instancia_nao_adquire_o_lock(
    admin_database_url: str,
    migrated_domain_schema: None,
) -> None:
    first_engine = create_async_engine(admin_database_url, pool_size=1, max_overflow=0)
    second_engine = create_async_engine(admin_database_url, pool_size=1, max_overflow=0)
    first = PostgresAdvisoryLock(first_engine)
    second = PostgresAdvisoryLock(second_engine)
    try:
        assert await first.try_acquire() is True
        assert await second.try_acquire() is False
        await first.release()
        assert await second.try_acquire() is True
        await second.release()
    finally:
        await first_engine.dispose()
        await second_engine.dispose()


async def test_release_e_idempotente(admin_database_url: str) -> None:
    engine = create_async_engine(admin_database_url, pool_size=1, max_overflow=0)
    lock = PostgresAdvisoryLock(engine)
    try:
        assert await lock.try_acquire() is True
        await lock.release()
        await lock.release()
        assert await lock.try_acquire() is True
    finally:
        await lock.release()
        await engine.dispose()
