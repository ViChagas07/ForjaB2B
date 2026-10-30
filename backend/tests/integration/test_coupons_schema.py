"""Schema e constraints de cupons (migration 0033).

Roda contra PostgreSQL real (Testcontainers) apos ``alembic upgrade head``.
Cobre o que a fase de modelagem promete: formato/unicidade do codigo, faixa de
percentual, snapshot no pedido, um cupom por pedido e RLS do resgate.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest

from .conftest import PostgresInstance

COMPANY_ID = uuid.UUID("dddd0000-0000-4000-8000-00000000d001")
USER_ID = uuid.UUID("dddd0000-0000-4000-8000-00000000d011")
ORDER_ID = uuid.UUID("dddd0000-0000-4000-8000-00000000d021")
CNPJ = "99888777000166"


def _connection(pg: PostgresInstance) -> psycopg.Connection:
    conn = pg.connect_admin(autocommit=False)
    conn.execute("SELECT app.set_tenant_context(%s, %s)", (COMPANY_ID, USER_ID))
    return conn


@contextmanager
def _tenant_tx(pg: PostgresInstance) -> Iterator[psycopg.Connection]:
    conn = _connection(pg)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def coupon_actor(pg: PostgresInstance, migrated_domain_schema: None) -> Iterator[None]:
    with _tenant_tx(pg) as conn:
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, 'Cupom Teste', 'ACTIVE') ON CONFLICT DO NOTHING",
            (COMPANY_ID, CNPJ),
        )
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
            "VALUES (%s, %s, 'coupon-admin@test.local', 'Cupom Admin', %s, 'ACTIVE') "
            "ON CONFLICT DO NOTHING",
            (USER_ID, COMPANY_ID, "c0" * 32),
        )
    try:
        yield
    finally:
        with _tenant_tx(pg) as conn:
            conn.execute("DELETE FROM coupon_redemptions WHERE company_id = %s", (COMPANY_ID,))
            conn.execute("DELETE FROM coupons WHERE created_by = %s", (USER_ID,))
            conn.execute("DELETE FROM orders WHERE company_id = %s", (COMPANY_ID,))
            conn.execute("DELETE FROM users WHERE id = %s", (USER_ID,))
            conn.execute("DELETE FROM companies WHERE id = %s", (COMPANY_ID,))


def _insert_coupon(
    conn: psycopg.Connection,
    *,
    code: str,
    percent: str = "10.00",
    coupon_type: str = "PRODUCT_TOTAL",
) -> uuid.UUID:
    row = conn.execute(
        "INSERT INTO coupons (code, type, percent, created_by) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (code, coupon_type, percent, USER_ID),
    ).fetchone()
    assert row is not None
    return row[0]


@pytest.mark.parametrize("percent", ["0", "-1", "100.01"])
def test_percentual_fora_da_faixa_e_rejeitado(
    pg: PostgresInstance, coupon_actor: None, percent: str
) -> None:
    conn = _connection(pg)
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert_coupon(
                conn, code=f"PCT-{percent.replace('.', 'X').replace('-', 'N')}", percent=percent
            )
        conn.rollback()
    finally:
        conn.close()


def test_codigo_duplicado_e_rejeitado(pg: PostgresInstance, coupon_actor: None) -> None:
    conn = _connection(pg)
    try:
        _insert_coupon(conn, code="CUPOM-DUPLICADO")
        conn.commit()
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (COMPANY_ID, USER_ID))
        with pytest.raises(psycopg.errors.UniqueViolation):
            _insert_coupon(conn, code="CUPOM-DUPLICADO")
        conn.rollback()
    finally:
        conn.close()


@pytest.mark.parametrize("code", ["abc", "AB", "COM ESPACO", "PONTO.10", "ÁBC1"])
def test_codigo_fora_do_formato_e_rejeitado(
    pg: PostgresInstance, coupon_actor: None, code: str
) -> None:
    conn = _connection(pg)
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert_coupon(conn, code=code)
        conn.rollback()
    finally:
        conn.close()


def test_um_cupom_por_pedido(pg: PostgresInstance, coupon_actor: None) -> None:
    conn = _connection(pg)
    try:
        conn.execute(
            "INSERT INTO orders (id, company_id, buyer_user_id, subtotal, total) "
            "VALUES (%s, %s, %s, 1000.00, 1000.00)",
            (ORDER_ID, COMPANY_ID, USER_ID),
        )
        coupon_id = _insert_coupon(conn, code="CUPOM-PEDIDO")
        conn.execute(
            "INSERT INTO coupon_redemptions "
            "(coupon_id, order_id, company_id, amount_discounted) "
            "VALUES (%s, %s, %s, 100.00)",
            (coupon_id, ORDER_ID, COMPANY_ID),
        )
        conn.commit()

        conn.execute("SELECT app.set_tenant_context(%s, %s)", (COMPANY_ID, USER_ID))
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(
                "INSERT INTO coupon_redemptions "
                "(coupon_id, order_id, company_id, amount_discounted) "
                "VALUES (%s, %s, %s, 100.00)",
                (coupon_id, ORDER_ID, COMPANY_ID),
            )
        conn.rollback()
    finally:
        conn.close()


def test_policy_de_leitura_admin_em_resgates(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    policies = {
        row[0]
        for row in admin_conn.execute(
            "SELECT polname FROM pg_policy WHERE polrelid = 'public.coupon_redemptions'::regclass"
        ).fetchall()
    }
    assert "coupon_redemptions_admin_read" in policies


def test_coupons_sem_rls_e_resgates_com_rls_tenant(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    rows = {
        row[0]: (row[1], row[2])
        for row in admin_conn.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity "
            "FROM pg_catalog.pg_class WHERE oid IN "
            "('public.coupons'::regclass, 'public.coupon_redemptions'::regclass)"
        ).fetchall()
    }
    assert rows["coupons"] == (False, False)
    assert rows["coupon_redemptions"] == (True, True)

    select_coupons = admin_conn.execute(
        "SELECT has_table_privilege('forja_app', 'public.coupons', 'SELECT')"
    ).fetchone()
    insert_coupons = admin_conn.execute(
        "SELECT has_table_privilege('forja_app', 'public.coupons', 'INSERT')"
    ).fetchone()
    assert select_coupons is not None and select_coupons[0] is True
    assert insert_coupons is not None and insert_coupons[0] is False
