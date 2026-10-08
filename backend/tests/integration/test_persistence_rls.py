"""Prova de isolamento multi-tenant nas tabelas de dominio da Fase 1.

Mesma estrategia dos testes de fundacao (rls_probe), agora sobre as tabelas
REAIS criadas pelas migrations: orders, companies e consent_records. O
catalogo global (products) deve permanecer legivel sem contexto de tenant.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest

from .conftest import PostgresInstance

COMPANY_A = uuid.UUID("caaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COMPANY_B = uuid.UUID("cbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B = uuid.UUID("22222222-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ORDER_A = uuid.UUID("33333333-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ORDER_B = uuid.UUID("44444444-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CATEGORY = uuid.UUID("66666666-cccc-cccc-cccc-cccccccccccc")
PRODUCT = uuid.UUID("55555555-cccc-cccc-cccc-cccccccccccc")


def _insert_company(conn: psycopg.Connection, company_id: uuid.UUID, cnpj: str, name: str) -> None:
    conn.execute(
        "INSERT INTO companies (id, cnpj, legal_name, status) VALUES (%s, %s, %s, 'ACTIVE')",
        (company_id, cnpj, name),
    )


def _insert_user(
    conn: psycopg.Connection,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    email: str,
    cpf_hash: str,
) -> None:
    conn.execute(
        "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
        "VALUES (%s, %s, %s, %s, %s, 'ACTIVE')",
        (user_id, company_id, email, email.split("@")[0], cpf_hash),
    )


def _insert_order(
    conn: psycopg.Connection,
    order_id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    conn.execute(
        "INSERT INTO orders (id, company_id, buyer_user_id, subtotal, total) "
        "VALUES (%s, %s, %s, %s, %s)",
        (order_id, company_id, user_id, Decimal("100.00"), Decimal("100.00")),
    )


@pytest.fixture(scope="module")
def domain_tenants(pg: PostgresInstance, migrated_domain_schema: None) -> Iterator[None]:
    admin = pg.connect_admin()
    try:
        # Catalogo global (sem RLS, sem contexto).
        admin.execute(
            "INSERT INTO categories (id, name, slug) VALUES (%s, 'Categoria RLS', 'categoria-rls') "
            "ON CONFLICT (id) DO NOTHING",
            (CATEGORY,),
        )
        admin.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, base_unit_price) "
            "VALUES (%s, %s, 'SKU-RLS', 'Produto RLS', 'produto-rls', %s) "
            "ON CONFLICT (id) DO NOTHING",
            (PRODUCT, CATEGORY, Decimal("10.00")),
        )

        tx = pg.connect_admin(autocommit=False)
        try:
            tx.execute("SELECT app.set_tenant_context(%s, %s)", (COMPANY_A, USER_A))
            _insert_company(tx, COMPANY_A, "19999999000191", "Empresa A")
            _insert_user(tx, USER_A, COMPANY_A, "usuario-a@teste.com", "a" * 64)
            _insert_order(tx, ORDER_A, COMPANY_A, USER_A)
            tx.commit()

            tx.execute("SELECT app.set_tenant_context(%s, %s)", (COMPANY_B, USER_B))
            _insert_company(tx, COMPANY_B, "19999999000192", "Empresa B")
            _insert_user(tx, USER_B, COMPANY_B, "usuario-b@teste.com", "b" * 64)
            _insert_order(tx, ORDER_B, COMPANY_B, USER_B)
            tx.commit()
        finally:
            tx.close()
        yield
    finally:
        admin.close()


def _app_tx(pg: PostgresInstance, tenant: uuid.UUID, user: uuid.UUID) -> psycopg.Connection:
    conn = pg.connect_app(autocommit=False)
    conn.execute("SELECT app.set_tenant_context(%s, %s)", (tenant, user))
    return conn


def test_tenant_a_ve_apenas_seus_pedidos(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = _app_tx(pg, COMPANY_A, USER_A)
    try:
        rows = conn.execute("SELECT id FROM orders ORDER BY id").fetchall()
        assert [r[0] for r in rows] == [ORDER_A]
        conn.commit()
    finally:
        conn.close()


def test_tenant_b_ve_apenas_seus_pedidos(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = _app_tx(pg, COMPANY_B, USER_B)
    try:
        rows = conn.execute("SELECT id FROM orders ORDER BY id").fetchall()
        assert [r[0] for r in rows] == [ORDER_B]
        conn.commit()
    finally:
        conn.close()


def test_sem_contexto_zero_linhas(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = pg.connect_app(autocommit=False)
    try:
        row = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
        assert row is not None and row[0] == 0
        conn.commit()
    finally:
        conn.close()


def test_empresa_ve_apenas_si_mesma(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = _app_tx(pg, COMPANY_A, USER_A)
    try:
        rows = conn.execute("SELECT id FROM companies ORDER BY id").fetchall()
        assert [r[0] for r in rows] == [COMPANY_A]
        conn.commit()
    finally:
        conn.close()


def test_insert_cross_tenant_negado(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = _app_tx(pg, COMPANY_A, USER_A)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            _insert_order(conn, uuid.uuid4(), COMPANY_B, USER_B)
        conn.rollback()
    finally:
        conn.close()


def test_update_cross_tenant_nao_alcanca(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = _app_tx(pg, COMPANY_A, USER_A)
    try:
        cur = conn.execute(
            "UPDATE orders SET status = 'DELIVERED' WHERE company_id = %s", (COMPANY_B,)
        )
        assert cur.rowcount == 0
        conn.commit()
    finally:
        conn.close()


def test_update_nao_pode_mover_para_outro_tenant(
    pg: PostgresInstance, domain_tenants: None
) -> None:
    conn = _app_tx(pg, COMPANY_A, USER_A)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "UPDATE orders SET company_id = %s WHERE company_id = %s",
                (COMPANY_B, COMPANY_A),
            )
        conn.rollback()
    finally:
        conn.close()


def test_delete_cross_tenant_nao_alcanca(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = _app_tx(pg, COMPANY_A, USER_A)
    try:
        cur = conn.execute("DELETE FROM orders WHERE company_id = %s", (COMPANY_B,))
        assert cur.rowcount == 0
        conn.commit()
    finally:
        conn.close()


def test_catalogo_global_visivel_sem_contexto(pg: PostgresInstance, domain_tenants: None) -> None:
    conn = pg.connect_app(autocommit=False)
    try:
        row = conn.execute("SELECT COUNT(*) FROM products").fetchone()
        assert row is not None and row[0] >= 1
        conn.commit()
    finally:
        conn.close()
