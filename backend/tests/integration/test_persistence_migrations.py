"""Testes de migracao: upgrade, downgrade e upgrade (round-trip).

Prova que o schema pode ser criado do zero, revertido e recriado de forma
deterministica. A verificacao de tabelas usa ``to_regclass`` via psycopg.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic.config import Config

from alembic import command

from .conftest import PostgresInstance

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _table_exists(conn: psycopg.Connection, table: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()
    return row is not None and row[0] is not None


def test_upgrade_downgrade_upgrade_roundtrip(
    admin_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    pg: PostgresInstance,
) -> None:
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_database_url)
    config = _alembic_config()

    command.upgrade(config, "head")
    admin = pg.connect_admin()
    try:
        assert _table_exists(admin, "orders") is True
        assert _table_exists(admin, "companies") is True
    finally:
        admin.close()

    command.downgrade(config, "base")
    admin = pg.connect_admin()
    try:
        assert _table_exists(admin, "orders") is False
        assert _table_exists(admin, "companies") is False
    finally:
        admin.close()

    command.upgrade(config, "head")
    admin = pg.connect_admin()
    try:
        assert _table_exists(admin, "orders") is True
        row = admin.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_catalog.pg_class "
            "WHERE oid = 'public.orders'::regclass"
        ).fetchone()
        assert row == (True, True)
    finally:
        admin.close()
