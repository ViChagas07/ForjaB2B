"""Migration 0042: upgrade do zero, banco populado, downgrade e role sem ownership.

A 0042 cria ``order_item_pricing`` em vez de alterar ``order_items``. O teste
cria um database descartavel, roda o Alembic do zero, popula a revisao 0041,
aplica a 0042, confere que nenhum dado antigo mudou, faz downgrade e reaplica.
O segundo teste repete a 0042 com uma role que NAO e owner de ``order_items``
(mas tem REFERENCES, como o cenario de producao), provando que o ALTER antigo
nao e mais executado.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field

import psycopg
import pytest
from alembic.config import Config
from psycopg import sql

from alembic import command

from .conftest import (
    ADMIN_PASSWORD,
    ADMIN_USER,
    APP_PASSWORD,
    APP_USER,
    BOOTSTRAP_PASSWORD,
    BOOTSTRAP_USER,
    DB_NAME,
    REPO_ROOT,
    PostgresInstance,
)

_COMPANY = uuid.UUID("c0c0c0c0-0000-4000-8000-000000000001")
_USER = uuid.UUID("c0c0c0c0-0000-4000-8000-000000000002")
_CATEGORY = uuid.UUID("c0c0c0c0-0000-4000-8000-000000000003")
_PRODUCT = uuid.UUID("c0c0c0c0-0000-4000-8000-000000000004")
_ORDER = uuid.UUID("c0c0c0c0-0000-4000-8000-000000000005")
_ITEM = uuid.UUID("c0c0c0c0-0000-4000-8000-000000000006")

_PRICING_COLUMNS = {
    "order_item_id",
    "list_unit_price",
    "list_line_total",
    "cnpj_discount_percent",
    "cnpj_discount_band",
    "cnpj_discount_amount",
}


@dataclass
class MigrationDatabase:
    """Database descartavel + roles criadas pelo teste (limpas no teardown)."""

    name: str
    roles: list[str] = field(default_factory=list)


def _run_psql(pg: PostgresInstance, database: str, args: list[str]) -> None:
    exit_code, output = pg.exec_in_container(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "--username",
            args[0],
            "--dbname",
            database,
            *args[1:],
        ]
    )
    assert exit_code == 0, output


def _bootstrap_database(pg: PostgresInstance, database: str) -> None:
    _run_psql(
        pg,
        database,
        [
            BOOTSTRAP_USER,
            "-v",
            f"app_user={APP_USER}",
            "-v",
            f"app_password={APP_PASSWORD}",
            "-v",
            f"admin_user={ADMIN_USER}",
            "-v",
            f"admin_password={ADMIN_PASSWORD}",
            "-v",
            f"db_name={database}",
            "-f",
            "/docker-entrypoint-initdb.d/sql/init-roles.sql",
        ],
    )
    _run_psql(
        pg,
        database,
        [
            ADMIN_USER,
            "-v",
            f"app_user={APP_USER}",
            "-v",
            f"admin_user={ADMIN_USER}",
            "-f",
            "/docker-entrypoint-initdb.d/sql/02-rls-setup.sql",
        ],
    )


@pytest.fixture()
def fresh_migration_database(pg: PostgresInstance) -> Iterator[MigrationDatabase]:
    database = f"forja_migration_{uuid.uuid4().hex[:10]}"
    bootstrap = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=DB_NAME, autocommit=True)
    try:
        bootstrap.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    finally:
        bootstrap.close()

    _bootstrap_database(pg, database)
    state = MigrationDatabase(name=database)
    try:
        yield state
    finally:
        cleanup = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=DB_NAME, autocommit=True)
        try:
            cleanup.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            cleanup.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database))
            )
            for role in reversed(state.roles):
                cleanup.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        finally:
            cleanup.close()


def _alembic_config(pg: PostgresInstance, database: str) -> Config:
    config = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        f"postgresql+asyncpg://{ADMIN_USER}:{ADMIN_PASSWORD}@{pg.host}:{pg.port}/{database}",
    )
    return config


def _seed_at_0041(pg: PostgresInstance, database: str) -> None:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO companies (id, cnpj, legal_name, status, account_type) "
                "VALUES (%s, '44555666000181', 'Migration Empresa', 'ACTIVE', 'COMPANY')",
                (_COMPANY,),
            )
            cur.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
                "VALUES (%s, %s, 'migration@teste.com', 'Migration User', %s, 'ACTIVE')",
                (_USER, _COMPANY, "a" * 64),
            )
            cur.execute(
                "INSERT INTO categories (id, name, slug, is_active) "
                "VALUES (%s, 'Migration Cat', 'migration-cat', true)",
                (_CATEGORY,),
            )
            cur.execute(
                "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
                "base_unit_price, min_order_qty) VALUES (%s, %s, 'MIG-001', "
                "'Produto Migration', 'mig-001', 'ACTIVE', false, 100.00, 1)",
                (_PRODUCT, _CATEGORY),
            )
            cur.execute(
                "INSERT INTO orders (id, company_id, buyer_user_id, subtotal, total) "
                "VALUES (%s, %s, %s, 100.00, 100.00)",
                (_ORDER, _COMPANY, _USER),
            )
            cur.execute(
                "INSERT INTO order_items (id, order_id, company_id, product_id, sku, "
                "product_name, quantity, unit_price, base_unit_price, tier_min_quantity, "
                "line_total) VALUES (%s, %s, %s, %s, 'MIG-001', 'Produto Migration', "
                "1, 100.00, 100.00, 1, 100.00)",
                (_ITEM, _ORDER, _COMPANY, _PRODUCT),
            )
        conn.commit()
    finally:
        conn.close()


def _item_row(pg: PostgresInstance, database: str) -> tuple[object, ...]:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sku, quantity, unit_price::text, line_total::text "
                "FROM order_items WHERE id = %s",
                (_ITEM,),
            )
            row = cur.fetchone()
            assert row is not None
            return row
    finally:
        conn.close()


def _pricing_columns(pg: PostgresInstance, database: str) -> set[str]:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'order_item_pricing'"
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def _pricing_fk(pg: PostgresInstance, database: str) -> tuple[str, str] | None:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT confrelid::regclass::text, confdeltype::text "
                "FROM pg_constraint WHERE conrelid = 'order_item_pricing'::regclass "
                "AND contype = 'f'"
            )
            row = cur.fetchone()
            return (row[0], row[1]) if row else None
    finally:
        conn.close()


def _pricing_count(pg: PostgresInstance, database: str) -> int:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM order_item_pricing")
            row = cur.fetchone()
            assert row is not None
            return int(row[0])
    finally:
        conn.close()


def _assert_old_item_preserved(pg: PostgresInstance, database: str) -> None:
    assert _item_row(pg, database) == ("MIG-001", 1, "100.00", "100.00")


def test_0042_upgrade_do_zero_populado_e_downgrade(
    pg: PostgresInstance,
    fresh_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = fresh_migration_database.name
    admin_url = f"postgresql+asyncpg://{ADMIN_USER}:{ADMIN_PASSWORD}@{pg.host}:{pg.port}/{database}"
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_url)
    config = _alembic_config(pg, database)

    # 1. Do zero: toda a cadeia ate a revisao imediatamente anterior.
    command.upgrade(config, "0041")
    assert _pricing_columns(pg, database) == set()

    # 2. Banco populado na 0041 (sem a tabela nova).
    _seed_at_0041(pg, database)
    _assert_old_item_preserved(pg, database)

    # 3. Upgrade 0042 cria a tabela nova e nao toca nos dados/colunas antigas.
    command.upgrade(config, "head")
    assert _pricing_columns(pg, database) == _PRICING_COLUMNS
    assert _pricing_fk(pg, database) == ("order_items", "c")
    _assert_old_item_preserved(pg, database)
    # Pedido antigo nao tem snapshot: ausencia = "sem snapshot".
    assert _pricing_count(pg, database) == 0

    # 4. Downgrade remove apenas a tabela nova.
    command.downgrade(config, "0041")
    assert _pricing_columns(pg, database) == set()
    _assert_old_item_preserved(pg, database)

    # 5. Reaplicar a 0042 continua seguro.
    command.upgrade(config, "head")
    assert _pricing_columns(pg, database) == _PRICING_COLUMNS
    assert _pricing_count(pg, database) == 0
    _assert_old_item_preserved(pg, database)


def _create_role(
    pg: PostgresInstance, database: MigrationDatabase, *, login: bool
) -> tuple[str, str | None]:
    role = f"forja_test_{uuid.uuid4().hex[:8]}"
    password = uuid.uuid4().hex if login else None
    bootstrap = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=DB_NAME, autocommit=True)
    try:
        if password is None:
            bootstrap.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        else:
            bootstrap.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
    finally:
        bootstrap.close()
    database.roles.append(role)
    return role, password


def _grant_migration_privileges(
    pg: PostgresInstance,
    database: MigrationDatabase,
    *,
    migration_role: str,
) -> None:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database.name, autocommit=True)
    try:
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database.name), sql.Identifier(migration_role)
            )
        )
        conn.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                sql.Identifier(migration_role)
            )
        )
        conn.execute(
            sql.SQL("GRANT USAGE ON SCHEMA app TO {}").format(sql.Identifier(migration_role))
        )
        conn.execute(
            sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO {}").format(
                sql.Identifier(migration_role)
            )
        )
        # REFERENCES simula o grant de producao; a role continua NÃO sendo owner.
        conn.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON TABLE public.order_items TO {}"
            ).format(sql.Identifier(migration_role))
        )
        conn.execute(
            sql.SQL("GRANT SELECT ON TABLE public.orders TO {}").format(
                sql.Identifier(migration_role)
            )
        )
        conn.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.alembic_version TO {}"
            ).format(sql.Identifier(migration_role))
        )
    finally:
        conn.close()


def test_0042_passa_com_role_nao_owner_de_order_items(
    pg: PostgresInstance,
    fresh_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = fresh_migration_database
    admin_url = (
        f"postgresql+asyncpg://{ADMIN_USER}:{ADMIN_PASSWORD}@{pg.host}:{pg.port}/{database.name}"
    )
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_url)
    config = _alembic_config(pg, database.name)
    command.upgrade(config, "0041")
    _seed_at_0041(pg, database.name)

    owner_role, _ = _create_role(pg, database, login=False)
    migration_role, migration_password = _create_role(pg, database, login=True)
    assert migration_password is not None

    bootstrap = pg.connect(
        BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database.name, autocommit=True
    )
    try:
        # Dono diferente: a role de migrations nao pode ALTER order_items.
        bootstrap.execute(
            sql.SQL("ALTER TABLE public.order_items OWNER TO {}").format(sql.Identifier(owner_role))
        )
    finally:
        bootstrap.close()
    _grant_migration_privileges(pg, database, migration_role=migration_role)

    conn = pg.connect(migration_role, migration_password, dbname=database.name, autocommit=False)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("ALTER TABLE public.order_items ADD COLUMN should_fail int")
    finally:
        conn.close()

    # A 0042 nao faz ALTER em order_items: cria a tabela nova e passa.
    migration_url = (
        f"postgresql+asyncpg://{migration_role}:{migration_password}"
        f"@{pg.host}:{pg.port}/{database.name}"
    )
    monkeypatch.setenv("DATABASE_ADMIN_URL", migration_url)
    command.upgrade(config, "head")

    assert _pricing_columns(pg, database.name) == _PRICING_COLUMNS
    assert _pricing_fk(pg, database.name) == ("order_items", "c")
    _assert_old_item_preserved(pg, database.name)

    command.downgrade(config, "0041")
    assert _pricing_columns(pg, database.name) == set()
    _assert_old_item_preserved(pg, database.name)
