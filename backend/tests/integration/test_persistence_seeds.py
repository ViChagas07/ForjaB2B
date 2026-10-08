"""Testes dos seeds deterministicos da Fase 1.

Valida banco vazio -> migrations -> seed -> dados esperados (empresa, usuarios,
produtos, CA expirado, credito de R$ 50.000 e tiers), alem da idempotencia.
"""

from __future__ import annotations

from decimal import Decimal

import psycopg

from app.infrastructure.db.seeds import (
    ADMIN_USER_ID,
    EXAMPLE_COMPANY_ID,
    EXAMPLE_CREDIT_LIMIT,
    PRODUCT_CAPACETE_ID,
    PRODUCT_LUVA_ID,
    PRODUCT_PARAFUSADEIRA_ID,
    PRODUCT_RESPIRADOR_ID,
    cpf_hash,
    seed_database,
)

from .conftest import PostgresInstance

_TEST_PEPPER = "test_pepper_for_seeds"


def _admin_tenant_conn(pg: PostgresInstance) -> psycopg.Connection:
    conn = pg.connect_admin(autocommit=False)
    conn.execute("SELECT app.set_tenant_context(%s, NULL)", (EXAMPLE_COMPANY_ID,))
    return conn


async def test_seeds_populam_empresa_e_usuarios(
    admin_database_url: str, migrated_domain_schema: None, pg: PostgresInstance
) -> None:
    await seed_database(admin_database_url, pepper=_TEST_PEPPER)

    conn = _admin_tenant_conn(pg)
    try:
        company = conn.execute(
            "SELECT cnpj, legal_name, status FROM companies WHERE id = %s",
            (EXAMPLE_COMPANY_ID,),
        ).fetchone()
        assert company == ("11444777000161", "Construtora Exemplo Ltda", "ACTIVE")

        members = conn.execute(
            """
            SELECT m.role
            FROM company_members m
            JOIN users u ON u.id = m.user_id
            WHERE u.company_id = %s
            """,
            (EXAMPLE_COMPANY_ID,),
        ).fetchall()
        assert {r[0] for r in members} == {"ADMIN", "BUYER", "APPROVER", "FINANCE"}

        admin_hash = conn.execute(
            "SELECT cpf_hash FROM users WHERE id = %s", (ADMIN_USER_ID,)
        ).fetchone()
        assert admin_hash is not None
        assert admin_hash[0] == cpf_hash("52998224725", _TEST_PEPPER)
        conn.commit()
    finally:
        conn.close()


async def test_seeds_ca_expirado_e_catalogo(
    admin_database_url: str, migrated_domain_schema: None, pg: PostgresInstance
) -> None:
    await seed_database(admin_database_url, pepper=_TEST_PEPPER)

    conn = pg.connect_admin()
    try:
        seed_products = (
            PRODUCT_CAPACETE_ID,
            PRODUCT_LUVA_ID,
            PRODUCT_RESPIRADOR_ID,
            PRODUCT_PARAFUSADEIRA_ID,
        )
        for product_id in seed_products:
            exists = conn.execute("SELECT 1 FROM products WHERE id = %s", (product_id,)).fetchone()
            assert exists is not None, f"produto seed ausente: {product_id}"

        expired = conn.execute(
            "SELECT is_epi, ca_valid_until < CURRENT_DATE FROM products WHERE id = %s",
            (PRODUCT_RESPIRADOR_ID,),
        ).fetchone()
        assert expired == (True, True), "respirador deve ser EPI com CA expirado"
    finally:
        conn.close()


async def test_seeds_credito_50000_e_ledger(
    admin_database_url: str, migrated_domain_schema: None, pg: PostgresInstance
) -> None:
    await seed_database(admin_database_url, pepper=_TEST_PEPPER)

    conn = _admin_tenant_conn(pg)
    try:
        limit = conn.execute(
            "SELECT credit_limit FROM credit_accounts WHERE company_id = %s",
            (EXAMPLE_COMPANY_ID,),
        ).fetchone()
        assert limit is not None and limit[0] == EXAMPLE_CREDIT_LIMIT

        ledger_sum = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM credit_entries WHERE company_id = %s",
            (EXAMPLE_COMPANY_ID,),
        ).fetchone()
        assert ledger_sum is not None and ledger_sum[0] == Decimal("50000.00")
        conn.commit()
    finally:
        conn.close()


async def test_seeds_tiers(
    admin_database_url: str, migrated_domain_schema: None, pg: PostgresInstance
) -> None:
    await seed_database(admin_database_url, pepper=_TEST_PEPPER)

    conn = pg.connect_admin()
    try:
        tiers = conn.execute(
            "SELECT min_quantity, max_quantity, unit_price FROM product_price_tiers "
            "WHERE product_id = %s ORDER BY min_quantity",
            (PRODUCT_CAPACETE_ID,),
        ).fetchall()
        assert tiers == [
            (6, 23, Decimal("24.90")),
            (24, None, Decimal("21.90")),
        ]
    finally:
        conn.close()


async def test_seeds_sao_idempotentes(
    admin_database_url: str, migrated_domain_schema: None, pg: PostgresInstance
) -> None:
    await seed_database(admin_database_url, pepper=_TEST_PEPPER)
    await seed_database(admin_database_url, pepper=_TEST_PEPPER)

    conn = _admin_tenant_conn(pg)
    try:
        companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        assert companies is not None and companies[0] == 1
        assert users is not None and users[0] == 4
        conn.commit()
    finally:
        conn.close()
