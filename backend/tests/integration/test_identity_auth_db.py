"""Testes de integracao da resolucao segura de identidade (SECURITY DEFINER).

Valida contra PostgreSQL real que:
- a funcao app.resolve_user_by_email e SECURITY DEFINER owned pela role
  dedicada forja_auth (NOLOGIN, NOBYPASSRLS);
- forja_app nao le users sem contexto (FORCE RLS), mas consegue resolver
  identidade APENAS via a funcao (retorno minimo de 4 colunas);
- a policy dedicada (migration 0006) existe e o GRANT e minimo (SELECT).

Usa dados de tenant DEDICADOS (nao os seeds globais), para nao interferir com
outros testes de persistencia que dependem do pepper dos seeds.
"""

from __future__ import annotations

import hashlib
import uuid

import psycopg
import pytest

from .conftest import PostgresInstance

_IDENTITY_COMPANY_ID = uuid.UUID("88888888-8888-4888-8888-888888888801")
_IDENTITY_USER_ID = uuid.UUID("88888888-8888-4888-8888-888888888802")
_IDENTITY_EMAIL = "resolve-me@teste.com"
_IDENTITY_CNPJ = "19999999000198"


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture()
def identity_probe_user(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    """Cria um usuario dedicado (ACTIVE, sem senha) para testar a resolucao."""
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_IDENTITY_COMPANY_ID,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_IDENTITY_COMPANY_ID, _IDENTITY_CNPJ, "Resolve Empresa Ltda"),
        )
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) "
            "VALUES (%s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (
                _IDENTITY_USER_ID,
                _IDENTITY_COMPANY_ID,
                _IDENTITY_EMAIL,
                "Resolve User",
                _cpf_hash(_IDENTITY_EMAIL),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_resolve_function_owned_por_forja_auth_e_security_definer(
    admin_conn: psycopg.Connection,
) -> None:
    row = admin_conn.execute(
        """
        SELECT pg_get_userbyid(p.proowner), p.prosecdef
        FROM pg_catalog.pg_proc p
        WHERE p.oid = 'app.resolve_user_by_email(text)'::regprocedure
        """
    ).fetchone()
    assert row == ("forja_auth", True)


def test_forja_auth_role_restrita_sem_login_sem_bypass(admin_conn: psycopg.Connection) -> None:
    row = admin_conn.execute(
        """
        SELECT rolcanlogin, rolsuper, rolbypassrls
        FROM pg_catalog.pg_roles
        WHERE rolname = 'forja_auth'
        """
    ).fetchone()
    assert row == (False, False, False)


def test_policy_users_auth_lookup_existe(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    row = admin_conn.execute(
        """
        SELECT 1 FROM pg_catalog.pg_policies
        WHERE schemaname = 'public' AND tablename = 'users' AND policyname = 'users_auth_lookup'
        """
    ).fetchone()
    assert row is not None


def test_forja_auth_tem_apenas_select_em_users(
    admin_conn: psycopg.Connection, migrated_domain_schema: None
) -> None:
    select = admin_conn.execute(
        "SELECT has_table_privilege('forja_auth', 'public.users', 'SELECT')"
    ).fetchone()
    insert = admin_conn.execute(
        "SELECT has_table_privilege('forja_auth', 'public.users', 'INSERT')"
    ).fetchone()
    assert select is not None and select[0] is True
    assert insert is not None and insert[0] is False


def test_app_resolve_user_por_email(pg: PostgresInstance, identity_probe_user: None) -> None:
    conn = pg.connect_app()
    try:
        row = conn.execute(
            "SELECT * FROM app.resolve_user_by_email(%s)", (_IDENTITY_EMAIL,)
        ).fetchone()
        assert row == (_IDENTITY_USER_ID, _IDENTITY_COMPANY_ID, "ACTIVE", None)
    finally:
        conn.close()


def test_app_resolve_user_inexistente_retorna_nada(
    pg: PostgresInstance, identity_probe_user: None
) -> None:
    conn = pg.connect_app()
    try:
        row = conn.execute(
            "SELECT * FROM app.resolve_user_by_email(%s)", ("ninguem@teste.com",)
        ).fetchone()
        assert row is None
    finally:
        conn.close()


def test_app_nao_le_users_sem_contexto(migrated_domain_schema: None, pg: PostgresInstance) -> None:
    """FORCE RLS: sem contexto, a leitura direta de users nao retorna nada."""
    conn = pg.connect_app()
    try:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        assert row is not None and row[0] == 0
    finally:
        conn.close()
