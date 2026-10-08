"""Prova de isolamento multi-tenant com RLS em PostgreSQL real.

A tabela rls_probe e uma FIXTURE exclusiva deste banco descartavel de testes:
nao faz parte do bootstrap permanente da aplicacao e nao representa dominio.
Ela existe apenas para comprovar ENABLE/FORCE ROW LEVEL SECURITY, policies
USING/WITH CHECK e o isolamento entre dois tenants.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from .conftest import PostgresInstance

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(scope="module")
def rls_probe(pg: PostgresInstance) -> Iterator[None]:
    """Cria a fixture RLS como forja_admin (owner NAO superuser).

    Os seeds sao inseridos pelo proprio admin sob FORCE RLS, o que tambem
    valida o caminho de backfill: DML administrativo exige contexto definido.
    """
    admin = pg.connect_admin()
    try:
        admin.execute(
            """
            CREATE TABLE public.rls_probe (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                company_id UUID NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        admin.execute("ALTER TABLE public.rls_probe ENABLE ROW LEVEL SECURITY")
        admin.execute("ALTER TABLE public.rls_probe FORCE ROW LEVEL SECURITY")
        admin.execute(
            """
            CREATE POLICY rls_probe_select ON public.rls_probe
            FOR SELECT USING (company_id = app.current_company_id())
            """
        )
        admin.execute(
            """
            CREATE POLICY rls_probe_insert ON public.rls_probe
            FOR INSERT WITH CHECK (company_id = app.current_company_id())
            """
        )
        admin.execute(
            """
            CREATE POLICY rls_probe_update ON public.rls_probe
            FOR UPDATE
            USING (company_id = app.current_company_id())
            WITH CHECK (company_id = app.current_company_id())
            """
        )
        admin.execute(
            """
            CREATE POLICY rls_probe_delete ON public.rls_probe
            FOR DELETE USING (company_id = app.current_company_id())
            """
        )

        admin_tx = pg.connect_admin(autocommit=False)
        try:
            admin_tx.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
            admin_tx.execute(
                "INSERT INTO public.rls_probe (company_id, payload) VALUES (%s, %s)",
                (TENANT_A, "tenant-a-1"),
            )
            admin_tx.execute(
                "INSERT INTO public.rls_probe (company_id, payload) VALUES (%s, %s)",
                (TENANT_A, "tenant-a-2"),
            )
            admin_tx.commit()

            admin_tx.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_B, USER_B))
            admin_tx.execute(
                "INSERT INTO public.rls_probe (company_id, payload) VALUES (%s, %s)",
                (TENANT_B, "tenant-b-1"),
            )
            admin_tx.commit()
        finally:
            admin_tx.close()

        yield
    finally:
        admin.close()


def _app_tx(pg: PostgresInstance, tenant: uuid.UUID, user: uuid.UUID) -> psycopg.Connection:
    conn = pg.connect_app(autocommit=False)
    conn.execute("SELECT app.set_tenant_context(%s, %s)", (tenant, user))
    return conn


def test_fixture_tem_rls_habilitado_e_forcado(pg: PostgresInstance, rls_probe: None) -> None:
    admin = pg.connect_admin()
    try:
        row = admin.execute(
            """
            SELECT c.relrowsecurity, c.relforcerowsecurity
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = 'rls_probe'
            """
        ).fetchone()
        assert row == (True, True)
    finally:
        admin.close()


def test_sem_contexto_nenhuma_linha_visivel(pg: PostgresInstance, rls_probe: None) -> None:
    conn = pg.connect_app(autocommit=False)
    try:
        row = conn.execute("SELECT COUNT(*) FROM public.rls_probe").fetchone()
        assert row is not None and row[0] == 0
        conn.commit()
    finally:
        conn.close()


def test_tenant_a_ve_apenas_proprias_linhas(pg: PostgresInstance, rls_probe: None) -> None:
    conn = _app_tx(pg, TENANT_A, USER_A)
    try:
        rows = conn.execute("SELECT payload FROM public.rls_probe ORDER BY payload").fetchall()
        assert [r[0] for r in rows] == ["tenant-a-1", "tenant-a-2"]
        conn.commit()
    finally:
        conn.close()


def test_tenant_b_ve_apenas_proprias_linhas(pg: PostgresInstance, rls_probe: None) -> None:
    conn = _app_tx(pg, TENANT_B, USER_B)
    try:
        rows = conn.execute("SELECT payload FROM public.rls_probe ORDER BY payload").fetchall()
        assert [r[0] for r in rows] == ["tenant-b-1"]
        conn.commit()
    finally:
        conn.close()


def test_insert_cruzado_negado_por_with_check(pg: PostgresInstance, rls_probe: None) -> None:
    conn = _app_tx(pg, TENANT_A, USER_A)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO public.rls_probe (company_id, payload) VALUES (%s, %s)",
                (TENANT_B, "fraude-cross-tenant"),
            )
        conn.rollback()
    finally:
        conn.close()


def test_update_cruzado_nao_alcanca_linhas_do_outro_tenant(
    pg: PostgresInstance, rls_probe: None
) -> None:
    conn = _app_tx(pg, TENANT_A, USER_A)
    try:
        cur = conn.execute(
            "UPDATE public.rls_probe SET payload = 'hijack' WHERE company_id = %s",
            (TENANT_B,),
        )
        assert cur.rowcount == 0
        conn.commit()
    finally:
        conn.close()


def test_update_nao_pode_mover_linha_para_outro_tenant(
    pg: PostgresInstance, rls_probe: None
) -> None:
    conn = _app_tx(pg, TENANT_A, USER_A)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "UPDATE public.rls_probe SET company_id = %s WHERE company_id = %s",
                (TENANT_B, TENANT_A),
            )
        conn.rollback()
    finally:
        conn.close()


def test_delete_cruzado_nao_alcanca_linhas_do_outro_tenant(
    pg: PostgresInstance, rls_probe: None
) -> None:
    conn = _app_tx(pg, TENANT_A, USER_A)
    try:
        cur = conn.execute("DELETE FROM public.rls_probe WHERE company_id = %s", (TENANT_B,))
        assert cur.rowcount == 0
        conn.commit()
    finally:
        conn.close()


def test_truncate_negado_para_runtime(pg: PostgresInstance, rls_probe: None) -> None:
    conn = _app_tx(pg, TENANT_A, USER_A)
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("TRUNCATE public.rls_probe")
        conn.rollback()
    finally:
        conn.close()


def test_force_rls_owner_sem_contexto_nao_ve_linhas(pg: PostgresInstance, rls_probe: None) -> None:
    """forja_admin e owner da tabela e NAO superuser: FORCE RLS se aplica."""
    admin = pg.connect_admin(autocommit=False)
    try:
        row = admin.execute("SELECT COUNT(*) FROM public.rls_probe").fetchone()
        assert row is not None and row[0] == 0
        admin.commit()
    finally:
        admin.close()


def test_force_rls_owner_com_contexto_ve_apenas_proprio_tenant(
    pg: PostgresInstance, rls_probe: None
) -> None:
    admin = pg.connect_admin(autocommit=False)
    try:
        admin.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_B, USER_B))
        rows = admin.execute("SELECT payload FROM public.rls_probe ORDER BY payload").fetchall()
        assert [r[0] for r in rows] == ["tenant-b-1"]
        admin.commit()
    finally:
        admin.close()
