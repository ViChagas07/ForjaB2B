"""Migration 0042: upgrade do zero, upgrade sobre banco populado e downgrade.

O teste cria um database descartavel dentro do PostgreSQL de integracao,
reexecuta o bootstrap real (roles/schema app) e roda o Alembic do zero. Depois
popula o schema na revisao 0041, aplica a 0042, confere que nenhum dado antigo
mudou, faz downgrade para 0041 e reaplica a 0042.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from alembic.config import Config

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
def fresh_migration_database(pg: PostgresInstance) -> Iterator[str]:
    database = f"forja_migration_{uuid.uuid4().hex[:10]}"
    bootstrap = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=DB_NAME, autocommit=True)
    try:
        bootstrap.execute(f'CREATE DATABASE "{database}"')
    finally:
        bootstrap.close()

    _bootstrap_database(pg, database)
    try:
        yield database
    finally:
        cleanup = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=DB_NAME, autocommit=True)
        try:
            cleanup.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            cleanup.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
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
            # to_jsonb evita erro quando a coluna ainda nao existe (0041):
            # a chave ausente vira NULL, permitindo comparar antes/depois.
            cur.execute(
                "SELECT sku, quantity, unit_price::text, line_total::text, "
                "to_jsonb(order_items) ->> 'list_unit_price', "
                "to_jsonb(order_items) ->> 'cnpj_discount_percent', "
                "to_jsonb(order_items) ->> 'cnpj_discount_band' "
                "FROM order_items WHERE id = %s",
                (_ITEM,),
            )
            row = cur.fetchone()
            assert row is not None
            return row
    finally:
        conn.close()


def _columns(pg: PostgresInstance, database: str) -> set[str]:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'order_items' "
                "AND column_name IN ('list_unit_price', 'cnpj_discount_percent', "
                "'cnpj_discount_band')"
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def test_0042_upgrade_do_zero_populado_e_downgrade(
    pg: PostgresInstance,
    fresh_migration_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = fresh_migration_database
    admin_url = f"postgresql+asyncpg://{ADMIN_USER}:{ADMIN_PASSWORD}@{pg.host}:{pg.port}/{database}"
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_url)
    config = _alembic_config(pg, database)

    # 1. Do zero: roda toda a cadeia ate a revisao imediatamente anterior.
    command.upgrade(config, "0041")
    assert _columns(pg, database) == set()

    # 2. Banco populado na 0041 (sem as colunas novas).
    _seed_at_0041(pg, database)
    before = _item_row(pg, database)
    assert before == ("MIG-001", 1, "100.00", "100.00", None, None, None)

    # 3. Upgrade 0042 preserva os dados e adiciona snapshot nullable.
    command.upgrade(config, "head")
    after_upgrade = _item_row(pg, database)
    assert after_upgrade == ("MIG-001", 1, "100.00", "100.00", None, None, None)
    assert _columns(pg, database) == {
        "list_unit_price",
        "cnpj_discount_percent",
        "cnpj_discount_band",
    }

    # 4. Downgrade remove apenas as colunas, sem apagar a linha.
    command.downgrade(config, "0041")
    assert _item_row(pg, database) == before
    assert _columns(pg, database) == set()

    # 5. Reaplicar a 0042 continua seguro e idempotente para os dados.
    command.upgrade(config, "head")
    assert _item_row(pg, database) == ("MIG-001", 1, "100.00", "100.00", None, None, None)
    assert _columns(pg, database) == {
        "list_unit_price",
        "cnpj_discount_percent",
        "cnpj_discount_band",
    }
