"""Testes de schema da Fase 1: tabelas, constraints, tipos monetarios e RLS.

Valida contra PostgreSQL real (Testcontainers) apos ``alembic upgrade head``.
Usa psycopg com a role administrativa para inspecionar o catalogo.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]

ALL_TABLES = {
    "companies",
    "company_addresses",
    "users",
    "company_members",
    "categories",
    "brands",
    "products",
    "product_price_tiers",
    "credit_accounts",
    "credit_entries",
    "orders",
    "order_items",
    "invoices",
    "consent_records",
    "audit_log",
}

TENANT_TABLES = {
    "companies",
    "company_addresses",
    "users",
    "company_members",
    "credit_accounts",
    "credit_entries",
    "orders",
    "order_items",
    "invoices",
    "consent_records",
    "audit_log",
}

GLOBAL_TABLES = {"categories", "brands", "products", "product_price_tiers"}


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _public_tables(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        return {r[0] for r in cur.fetchall()}


def test_todas_as_tabelas_de_dominio_existem(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    assert _public_tables(admin_conn) >= ALL_TABLES


@pytest.mark.parametrize(
    ("table", "column", "precision"),
    [
        ("products", "base_unit_price", 12),
        ("product_price_tiers", "unit_price", 12),
        ("orders", "subtotal", 14),
        ("orders", "total", 14),
        ("order_items", "unit_price", 12),
        ("order_items", "line_total", 14),
        ("invoices", "amount", 14),
        ("credit_accounts", "credit_limit", 14),
        ("credit_entries", "amount", 14),
    ],
)
def test_money_usam_numeric_nao_float(
    admin_conn: psycopg.Connection,
    migrated_domain_schema: None,
    table: str,
    column: str,
    precision: int,
) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
            """,
            (table, column),
        )
        row = cur.fetchone()
    assert row is not None, f"{table}.{column} nao existe"
    data_type, numeric_precision, numeric_scale = row
    assert data_type == "numeric"
    assert numeric_precision == precision
    assert numeric_scale == 2


@pytest.mark.parametrize(
    ("constraint_name", "table"),
    [
        ("uq_companies_cnpj", "companies"),
        ("uq_users_email", "users"),
        ("uq_users_cpf_hash", "users"),
        ("uq_products_sku", "products"),
        ("uq_products_slug", "products"),
        ("uq_invoices_number", "invoices"),
        ("uq_company_members_company_user", "company_members"),
        ("uq_product_price_tiers_product_min_qty", "product_price_tiers"),
    ],
)
def test_constraints_de_unicidade(
    admin_conn: psycopg.Connection,
    migrated_domain_schema: None,
    constraint_name: str,
    table: str,
) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_catalog.pg_constraint c
            JOIN pg_catalog.pg_class t ON t.oid = c.conrelid
            WHERE c.conname = %s AND t.relname = %s
            """,
            (constraint_name, table),
        )
        assert cur.fetchone() is not None, f"constraint {constraint_name} ausente em {table}"


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("companies", "status"),
        ("users", "status"),
        ("company_members", "role"),
        ("products", "status"),
        ("orders", "status"),
        ("invoices", "status"),
        ("invoices", "payment_terms"),
        ("credit_entries", "entry_type"),
        ("consent_records", "purpose"),
        ("consent_records", "action"),
    ],
)
def test_enums_tem_check_constraint(
    admin_conn: psycopg.Connection,
    migrated_domain_schema: None,
    table: str,
    column: str,
) -> None:
    expected_name = f"ck_{table}_{column}"
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_catalog.pg_constraint c
            JOIN pg_catalog.pg_class t ON t.oid = c.conrelid
            WHERE c.conname = %s AND t.relname = %s AND c.contype = 'c'
            """,
            (expected_name, table),
        )
        assert cur.fetchone() is not None, f"check {expected_name} ausente em {table}"


def test_tabelas_tenant_tem_rls_habilitado_e_forcado(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            """,
            (sorted(TENANT_TABLES),),
        )
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    assert set(rows) == TENANT_TABLES, f"tabelas tenant ausentes: {TENANT_TABLES - set(rows)}"
    for table, (rls, force) in rows.items():
        assert (rls, force) == (True, True), f"{table}: rls={rls} force={force}"


def test_catalogo_global_sem_rls(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname, c.relrowsecurity
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            """,
            (sorted(GLOBAL_TABLES),),
        )
        rows = {r[0]: r[1] for r in cur.fetchall()}
    assert set(rows) == GLOBAL_TABLES
    for table, rls in rows.items():
        assert rls is False, f"{table} nao deveria ter RLS"


def test_runtime_somente_leitura_no_catalogo_global(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    for table in sorted(GLOBAL_TABLES):
        select = admin_conn.execute(
            "SELECT has_table_privilege('forja_app', %s, 'SELECT')", (f"public.{table}",)
        ).fetchone()
        insert = admin_conn.execute(
            "SELECT has_table_privilege('forja_app', %s, 'INSERT')", (f"public.{table}",)
        ).fetchone()
        assert select is not None and select[0] is True
        assert insert is not None and insert[0] is False, f"forja_app nao pode inserir em {table}"


def test_model_metadata_sem_drift(
    migrated_domain_schema: None,
    admin_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Base.metadata deve corresponder exatamente ao schema migrado (sem drift)."""
    monkeypatch.setenv("DATABASE_ADMIN_URL", admin_database_url)
    config = _alembic_config()
    try:
        command.check(config)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        pytest.fail(f"drift entre models e migrations (alembic check saiu com {code})")
