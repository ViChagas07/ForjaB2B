"""Testes do bootstrap real: roles, privilegios, ownership, ACLs e helpers."""

from __future__ import annotations

import psycopg
import pytest

from .conftest import ADMIN_USER, APP_USER, DB_NAME


def _role_attrs(conn: psycopg.Connection, role: str) -> dict[str, bool]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole,
                   rolinherit, rolreplication, rolcanlogin
            FROM pg_catalog.pg_roles
            WHERE rolname = %s
            """,
            (role,),
        )
        row = cur.fetchone()
    assert row is not None, f"role inexistente: {role}"
    keys = (
        "rolsuper",
        "rolbypassrls",
        "rolcreatedb",
        "rolcreaterole",
        "rolinherit",
        "rolreplication",
        "rolcanlogin",
    )
    return dict(zip(keys, row, strict=True))


def test_roles_existem(admin_conn: psycopg.Connection) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            "SELECT rolname FROM pg_catalog.pg_roles WHERE rolname = ANY(%s) ORDER BY 1",
            ([APP_USER, ADMIN_USER],),
        )
        found = [r[0] for r in cur.fetchall()]
    assert found == sorted([APP_USER, ADMIN_USER])


def test_runtime_app_sem_privilegios_de_cluster_e_sujeita_a_rls(
    admin_conn: psycopg.Connection,
) -> None:
    attrs = _role_attrs(admin_conn, APP_USER)
    assert attrs == {
        "rolsuper": False,
        "rolbypassrls": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolinherit": False,
        "rolreplication": False,
        "rolcanlogin": True,
    }


def test_admin_restrito_nao_e_superuser_nem_bypassrls(
    admin_conn: psycopg.Connection,
) -> None:
    attrs = _role_attrs(admin_conn, ADMIN_USER)
    assert attrs["rolsuper"] is False
    assert attrs["rolbypassrls"] is False
    assert attrs["rolcreatedb"] is False
    assert attrs["rolcreaterole"] is False
    assert attrs["rolreplication"] is False
    assert attrs["rolcanlogin"] is True


def test_runtime_sem_memberships_indevidos(admin_conn: psycopg.Connection) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT parent.rolname
            FROM pg_catalog.pg_auth_members m
            JOIN pg_catalog.pg_roles child ON child.oid = m.member
            JOIN pg_catalog.pg_roles parent ON parent.oid = m.roleid
            WHERE child.rolname = %s
            """,
            (APP_USER,),
        )
        memberships = [r[0] for r in cur.fetchall()]
    assert memberships == []


def test_database_owned_pelo_admin_e_connect_restrito(
    admin_conn: psycopg.Connection,
) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_userbyid(d.datdba)
            FROM pg_catalog.pg_database d
            WHERE d.datname = %s
            """,
            (DB_NAME,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == ADMIN_USER

    for role in (APP_USER, ADMIN_USER):
        grant = admin_conn.execute(
            "SELECT has_database_privilege(%s, %s, 'CONNECT')", (role, DB_NAME)
        ).fetchone()
        assert grant is not None and grant[0] is True


def test_extensoes_base_instaladas(admin_conn: psycopg.Connection) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            "SELECT extname FROM pg_catalog.pg_extension WHERE extname = ANY(%s) ORDER BY 1",
            (["uuid-ossp", "pgcrypto"],),
        )
        found = [r[0] for r in cur.fetchall()]
    assert found == ["pgcrypto", "uuid-ossp"]


def test_schema_app_owned_pelo_admin(admin_conn: psycopg.Connection) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_userbyid(n.nspowner)
            FROM pg_catalog.pg_namespace n
            WHERE n.nspname = 'app'
            """
        )
        row = cur.fetchone()
    assert row is not None and row[0] == ADMIN_USER


@pytest.mark.parametrize(
    "function_signature",
    [
        "app.current_company_id()",
        "app.current_user_id()",
        "app.set_tenant_context(uuid, uuid)",
    ],
)
def test_helpers_owned_pelo_admin_e_execucao_restrita(
    admin_conn: psycopg.Connection, function_signature: str
) -> None:
    """Owner = forja_admin; EXECUTE negado a PUBLIC e concedido a forja_app."""
    with admin_conn.cursor() as cur:
        cur.execute(
            "SELECT pg_get_userbyid(p.proowner) FROM pg_catalog.pg_proc p "
            "WHERE p.oid = %s::regprocedure",
            (function_signature,),
        )
        owner_row = cur.fetchone()

        # aclexplode: grantee = 0 representa PUBLIC.
        cur.execute(
            """
            SELECT COUNT(*)
            FROM pg_catalog.pg_proc p,
                 aclexplode(p.proacl) acl
            WHERE p.oid = %s::regprocedure
              AND acl.grantee = 0
              AND acl.privilege_type = 'EXECUTE'
            """,
            (function_signature,),
        )
        public_row = cur.fetchone()

    assert owner_row is not None
    assert public_row is not None
    assert owner_row[0] == ADMIN_USER
    assert public_row[0] == 0
    grant = admin_conn.execute(
        "SELECT has_function_privilege(%s, %s::regprocedure, 'EXECUTE')",
        (APP_USER, function_signature),
    ).fetchone()
    assert grant is not None and grant[0] is True


def test_default_privileges_tabelas_dml_para_runtime(
    admin_conn: psycopg.Connection,
) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT acl.privilege_type
            FROM pg_catalog.pg_default_acl d
            JOIN pg_catalog.pg_roles r ON r.oid = d.defaclrole
            CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
            JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl.grantee
            JOIN pg_catalog.pg_namespace n ON n.oid = d.defaclnamespace
            WHERE r.rolname = %s
              AND n.nspname = 'public'
              AND d.defaclobjtype = 'r'
              AND grantee.rolname = %s
            """,
            (ADMIN_USER, APP_USER),
        )
        privileges = {r[0] for r in cur.fetchall()}
    assert privileges == {"SELECT", "INSERT", "UPDATE", "DELETE"}


def test_default_privileges_sequences_sem_update(admin_conn: psycopg.Connection) -> None:
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT acl.privilege_type
            FROM pg_catalog.pg_default_acl d
            JOIN pg_catalog.pg_roles r ON r.oid = d.defaclrole
            CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
            JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl.grantee
            JOIN pg_catalog.pg_namespace n ON n.oid = d.defaclnamespace
            WHERE r.rolname = %s
              AND n.nspname = 'public'
              AND d.defaclobjtype = 'S'
              AND grantee.rolname = %s
            """,
            (ADMIN_USER, APP_USER),
        )
        privileges = {r[0] for r in cur.fetchall()}
    assert privileges == {"USAGE", "SELECT"}


def test_default_privileges_funcoes_sem_public(admin_conn: psycopg.Connection) -> None:
    """Default privileges de funcoes: sem grant a PUBLIC, EXECUTE ao runtime."""
    with admin_conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT acl.grantee, acl.privilege_type
            FROM pg_catalog.pg_default_acl d
            JOIN pg_catalog.pg_roles r ON r.oid = d.defaclrole
            CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
            JOIN pg_catalog.pg_namespace n ON n.oid = d.defaclnamespace
            WHERE r.rolname = %s
              AND n.nspname IN ('public', 'app')
              AND d.defaclobjtype = 'f'
            """,
            (ADMIN_USER,),
        )
        rows = cur.fetchall()
    public_grants = [p for grantee, p in rows if grantee == 0]
    assert public_grants == []


def test_runtime_nao_pode_criar_schema_nem_tabela(
    app_conn: psycopg.Connection,
) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("CREATE SCHEMA rls_probe_forbidden_schema")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("CREATE TABLE public.rls_probe_forbidden_table (id int)")
