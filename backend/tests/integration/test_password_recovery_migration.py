"""Migration 0043: telefones verificados, estado de credencial e RLS.

Cria um database descartavel com o bootstrap real, aplica a cadeia ate 0043,
confere estrutura/RLS/grants/funcao, testa a resolucao nao autenticada por
telefone, o isolamento entre tenants e o ciclo downgrade/upgrade.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

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
    PostgresInstance,
)
from .test_cnpj_migration import (
    MigrationDatabase,
    _alembic_config,
    _bootstrap_database,
    _create_role,
)

_COMPANY_A = uuid.UUID("d0d0d0d0-0000-4000-8000-000000000001")
_COMPANY_B = uuid.UUID("d0d0d0d0-0000-4000-8000-000000000002")
_USER_A = uuid.UUID("d0d0d0d0-0000-4000-8000-000000000003")
_USER_B = uuid.UUID("d0d0d0d0-0000-4000-8000-000000000004")
_USER_INACTIVE = uuid.UUID("d0d0d0d0-0000-4000-8000-000000000005")
_PHONE_A = "+5511900000001"
_PHONE_B = "+5511900000002"
_PHONE_INACTIVE = "+5511900000003"


@pytest.fixture()
def recovery_migration_database(pg: PostgresInstance) -> Iterator[MigrationDatabase]:
    """Database descartavel com o bootstrap real (roles, schema app, funcoes)."""
    database = f"forja_recovery_{uuid.uuid4().hex[:10]}"
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


def _admin_url(pg: PostgresInstance, database: str) -> str:
    return f"postgresql+asyncpg://{ADMIN_USER}:{ADMIN_PASSWORD}@{pg.host}:{pg.port}/{database}"


def _app_conn(
    pg: PostgresInstance, database: str, *, autocommit: bool = True
) -> psycopg.Connection:
    return pg.connect(APP_USER, APP_PASSWORD, dbname=database, autocommit=autocommit)


def _scalar(pg: PostgresInstance, database: str, sql: str, params: tuple[Any, ...] = ()) -> Any:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database)
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def _table_exists(pg: PostgresInstance, database: str, table: str) -> bool:
    return bool(_scalar(pg, database, "SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",)))


def _function_exists(pg: PostgresInstance, database: str, signature: str) -> bool:
    return bool(_scalar(pg, database, "SELECT to_regprocedure(%s) IS NOT NULL", (signature,)))


def _grant_restricted_migration_privileges(pg: PostgresInstance, database: str, role: str) -> None:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database, autocommit=True)
    try:
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(role)
            )
        )
        conn.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(role))
        )
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA app TO {}").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO {}").format(
                sql.Identifier(role)
            )
        )
        conn.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.alembic_version TO {}"
            ).format(sql.Identifier(role))
        )
    finally:
        conn.close()


def _seed_tenants(pg: PostgresInstance, database: str) -> None:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database)
    try:
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status, account_type) VALUES "
            "(%s, '44555666000191', 'Recovery Empresa A', 'ACTIVE', 'COMPANY'), "
            "(%s, '44555666000192', 'Recovery Empresa B', 'ACTIVE', 'COMPANY')",
            (_COMPANY_A, _COMPANY_B),
        )
        conn.execute(
            "INSERT INTO users (id, company_id, email, full_name, cpf_hash, status) VALUES "
            "(%s, %s, 'recovery-a@teste.com', 'Recovery A', %s, 'ACTIVE'), "
            "(%s, %s, 'recovery-b@teste.com', 'Recovery B', %s, 'ACTIVE'), "
            "(%s, %s, 'recovery-inactive@teste.com', 'Recovery Inactive', %s, 'SUSPENDED')",
            (
                _USER_A,
                _COMPANY_A,
                "1" * 64,
                _USER_B,
                _COMPANY_B,
                "2" * 64,
                _USER_INACTIVE,
                _COMPANY_A,
                "3" * 64,
            ),
        )
    finally:
        conn.close()


def _insert_verified_contacts(pg: PostgresInstance, database: str) -> None:
    conn = _app_conn(pg, database, autocommit=False)
    try:
        for company_id, user_id, phone in (
            (_COMPANY_A, _USER_A, _PHONE_A),
            (_COMPANY_B, _USER_B, _PHONE_B),
            (_COMPANY_A, _USER_INACTIVE, _PHONE_INACTIVE),
        ):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            conn.execute(
                "INSERT INTO user_verified_phones "
                "(user_id, company_id, phone_e164, verified_at) VALUES (%s, %s, %s, %s)",
                (user_id, company_id, phone, datetime.now(UTC)),
            )
            conn.execute(
                "INSERT INTO user_credential_state (user_id, company_id) VALUES (%s, %s)",
                (user_id, company_id),
            )
        conn.commit()
    finally:
        conn.close()


def _rls_flags(pg: PostgresInstance, database: str, table: str) -> tuple[bool, bool]:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database)
    try:
        row = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
            (f"public.{table}",),
        ).fetchone()
        assert row is not None
        return bool(row[0]), bool(row[1])
    finally:
        conn.close()


def _policy_names(pg: PostgresInstance, database: str, table: str) -> set[str]:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database)
    try:
        rows = conn.execute(
            "SELECT polname FROM pg_policy WHERE polrelid = %s::regclass",
            (f"public.{table}",),
        ).fetchall()
        return {str(row[0]) for row in rows}
    finally:
        conn.close()


def _constraint_names(pg: PostgresInstance, database: str, table: str) -> set[str]:
    conn = pg.connect(BOOTSTRAP_USER, BOOTSTRAP_PASSWORD, dbname=database)
    try:
        rows = conn.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass",
            (f"public.{table}",),
        ).fetchall()
        return {str(row[0]) for row in rows}
    finally:
        conn.close()


def test_0043_cria_estrutura_com_rls_e_downgrade_remove(
    pg: PostgresInstance,
    recovery_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = recovery_migration_database.name
    monkeypatch.setenv("DATABASE_ADMIN_URL", _admin_url(pg, database))
    config = _alembic_config(pg, database)

    command.upgrade(config, "0042")
    command.upgrade(config, "head")

    for table in ("user_verified_phones", "user_credential_state"):
        assert _table_exists(pg, database, table)
        assert _rls_flags(pg, database, table) == (True, True)

    phone_policies = _policy_names(pg, database, "user_verified_phones")
    assert {
        "user_verified_phones_select",
        "user_verified_phones_insert",
        "user_verified_phones_update",
        "user_verified_phones_delete",
        "user_verified_phones_auth_lookup",
        "user_verified_phones_auth_manage",
    } <= phone_policies

    state_policies = _policy_names(pg, database, "user_credential_state")
    assert {
        "user_credential_state_select",
        "user_credential_state_insert",
        "user_credential_state_update",
        "user_credential_state_delete",
    } <= state_policies

    phone_constraints = _constraint_names(pg, database, "user_verified_phones")
    assert "uq_user_verified_phones_user_id" in phone_constraints
    assert "uq_user_verified_phones_phone_e164" in phone_constraints
    state_constraints = _constraint_names(pg, database, "user_credential_state")
    assert "ck_user_credential_state_credential_epoch_non_negative" in state_constraints

    assert _scalar(
        pg,
        database,
        "SELECT has_table_privilege(%s, %s, 'SELECT,INSERT,UPDATE,DELETE')",
        (APP_USER, "public.user_verified_phones"),
    )
    assert _scalar(
        pg,
        database,
        "SELECT has_table_privilege(%s, %s, 'SELECT,INSERT,UPDATE,DELETE')",
        (APP_USER, "public.user_credential_state"),
    )
    assert _function_exists(pg, database, "public.resolve_user_by_verified_phone(text)")
    assert (
        _scalar(
            pg,
            database,
            "SELECT pg_get_userbyid(p.proowner) FROM pg_proc p "
            "WHERE p.oid = 'public.resolve_user_by_verified_phone(text)'::regprocedure",
        )
        == "forja_auth"
    )
    assert _scalar(
        pg,
        database,
        "SELECT p.prosecdef FROM pg_proc p "
        "WHERE p.oid = 'public.resolve_user_by_verified_phone(text)'::regprocedure",
    )
    assert _scalar(
        pg,
        database,
        "SELECT has_function_privilege(%s, "
        "'public.resolve_user_by_verified_phone(text)'::regprocedure, 'EXECUTE')",
        (APP_USER,),
    )
    assert _function_exists(pg, database, "public.claim_verified_phone(text,uuid,uuid)")
    assert (
        _scalar(
            pg,
            database,
            "SELECT pg_get_userbyid(p.proowner) FROM pg_proc p "
            "WHERE p.oid = 'public.claim_verified_phone(text,uuid,uuid)'::regprocedure",
        )
        == "forja_auth"
    )
    assert _scalar(
        pg,
        database,
        "SELECT has_function_privilege(%s, "
        "'public.claim_verified_phone(text,uuid,uuid)'::regprocedure, 'EXECUTE')",
        (APP_USER,),
    )

    command.downgrade(config, "0042")
    for table in ("user_verified_phones", "user_credential_state"):
        assert not _table_exists(pg, database, table)
    assert not _function_exists(pg, database, "public.resolve_user_by_verified_phone(text)")

    command.upgrade(config, "head")
    for table in ("user_verified_phones", "user_credential_state"):
        assert _table_exists(pg, database, table)


def test_0043_resolve_telefone_ativo_e_isola_tenants(
    pg: PostgresInstance,
    recovery_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = recovery_migration_database.name
    monkeypatch.setenv("DATABASE_ADMIN_URL", _admin_url(pg, database))
    config: Config = _alembic_config(pg, database)

    command.upgrade(config, "head")
    _seed_tenants(pg, database)
    _insert_verified_contacts(pg, database)

    anonymous = _app_conn(pg, database)
    try:
        row = anonymous.execute(
            "SELECT user_id, company_id FROM public.resolve_user_by_verified_phone(%s)",
            (_PHONE_A,),
        ).fetchone()
        assert row == (_USER_A, _COMPANY_A)

        # A funcao resolve o telefone verificado; o filtro de conta ACTIVE
        # acontece no fluxo de envio, depois de resolver o tenant.
        assert anonymous.execute(
            "SELECT user_id, company_id FROM public.resolve_user_by_verified_phone(%s)",
            (_PHONE_INACTIVE,),
        ).fetchone() == (_USER_INACTIVE, _COMPANY_A)
        assert (
            anonymous.execute(
                "SELECT user_id FROM public.resolve_user_by_verified_phone(%s)",
                ("+5511900000009",),
            ).fetchone()
            is None
        )

        # Sem contexto de tenant, o runtime nao le a tabela diretamente.
        assert anonymous.execute("SELECT count(*) FROM user_verified_phones").fetchone() == (0,)
        assert anonymous.execute("SELECT count(*) FROM user_credential_state").fetchone() == (0,)
    finally:
        anonymous.close()

    tenant_b = _app_conn(pg, database, autocommit=False)
    try:
        tenant_b.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        phones = tenant_b.execute(
            "SELECT phone_e164 FROM user_verified_phones ORDER BY phone_e164"
        ).fetchall()
        assert phones == [(_PHONE_B,)]
        states = tenant_b.execute("SELECT user_id FROM user_credential_state").fetchall()
        assert states == [(_USER_B,)]
        tenant_b.commit()
    finally:
        tenant_b.close()

    # Telefone e globalmente unico: outra empresa nao pode reaproveitar.
    duplicate = _app_conn(pg, database, autocommit=False)
    try:
        duplicate.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        with pytest.raises(psycopg.errors.UniqueViolation):
            duplicate.execute(
                "INSERT INTO user_verified_phones "
                "(user_id, company_id, phone_e164, verified_at) VALUES (%s, %s, %s, %s)",
                (_USER_B, _COMPANY_B, _PHONE_A, datetime.now(UTC)),
            )
        duplicate.rollback()
    finally:
        duplicate.close()


def test_0043_funciona_sem_membership_de_forja_auth(
    pg: PostgresInstance,
    recovery_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Role restrita (sem membership) mantem a funcao funcional com fallback."""
    database = recovery_migration_database.name
    monkeypatch.setenv("DATABASE_ADMIN_URL", _admin_url(pg, database))
    config = _alembic_config(pg, database)
    command.upgrade(config, "0042")
    _seed_tenants(pg, database)

    restricted_role, password = _create_role(pg, recovery_migration_database, login=True)
    assert password is not None
    _grant_restricted_migration_privileges(pg, database, restricted_role)

    restricted_url = (
        f"postgresql+asyncpg://{restricted_role}:{password}@{pg.host}:{pg.port}/{database}"
    )
    monkeypatch.setenv("DATABASE_ADMIN_URL", restricted_url)
    command.upgrade(config, "head")

    assert (
        _scalar(
            pg,
            database,
            "SELECT pg_get_userbyid(p.proowner) FROM pg_proc p "
            "WHERE p.oid = 'public.resolve_user_by_verified_phone(text)'::regprocedure",
        )
        == restricted_role
    )
    assert "user_verified_phones_owner_lookup" in _policy_names(
        pg, database, "user_verified_phones"
    )

    conn = _app_conn(pg, database, autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_A,))
        conn.execute(
            "INSERT INTO user_verified_phones "
            "(user_id, company_id, phone_e164, verified_at) VALUES (%s, %s, %s, %s)",
            (_USER_A, _COMPANY_A, _PHONE_A, datetime.now(UTC)),
        )
        conn.commit()
    finally:
        conn.close()

    lookup = _app_conn(pg, database)
    try:
        assert lookup.execute(
            "SELECT user_id, company_id FROM public.resolve_user_by_verified_phone(%s)",
            (_PHONE_A,),
        ).fetchone() == (_USER_A, _COMPANY_A)
    finally:
        lookup.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_0044_claim_move_telefone_entre_usuarios(
    pg: PostgresInstance,
    recovery_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = recovery_migration_database.name
    monkeypatch.setenv("DATABASE_ADMIN_URL", _admin_url(pg, database))
    config = _alembic_config(pg, database)
    command.upgrade(config, "head")
    _seed_tenants(pg, database)
    _insert_verified_contacts(pg, database)

    app_conn = _app_conn(pg, database, autocommit=False)
    try:
        app_conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        previous = app_conn.execute(
            "SELECT previous_user_id, previous_company_id "
            "FROM public.claim_verified_phone(%s, %s, %s)",
            (_PHONE_A, _USER_B, _COMPANY_B),
        ).fetchone()
        assert previous == (_USER_A, _COMPANY_A)

        app_conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_A,))
        assert app_conn.execute(
            "SELECT count(*) FROM user_verified_phones WHERE user_id = %s",
            (_USER_A,),
        ).fetchone() == (0,)
        app_conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        assert app_conn.execute(
            "SELECT phone_e164 FROM user_verified_phones WHERE user_id = %s",
            (_USER_B,),
        ).fetchone() == (_PHONE_A,)

        # Reivindicar o mesmo telefone pelo mesmo usuario nao devolve dono anterior.
        app_conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        same = app_conn.execute(
            "SELECT previous_user_id FROM public.claim_verified_phone(%s, %s, %s)",
            (_PHONE_A, _USER_B, _COMPANY_B),
        ).fetchone()
        assert same == (None,)
        app_conn.commit()
    finally:
        app_conn.close()


def test_0044_corrida_de_reivindicacao_nao_gera_erro(
    pg: PostgresInstance,
    recovery_migration_database: MigrationDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = recovery_migration_database.name
    monkeypatch.setenv("DATABASE_ADMIN_URL", _admin_url(pg, database))
    config = _alembic_config(pg, database)
    command.upgrade(config, "head")
    _seed_tenants(pg, database)
    _insert_verified_contacts(pg, database)

    import threading

    results: list[object] = []
    errors: list[BaseException] = []

    def claim(user_id: uuid.UUID, company_id: uuid.UUID) -> None:
        conn = _app_conn(pg, database, autocommit=False)
        try:
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            row = conn.execute(
                "SELECT previous_user_id FROM public.claim_verified_phone(%s, %s, %s)",
                (_PHONE_A, user_id, company_id),
            ).fetchone()
            conn.commit()
            results.append(row)
        except BaseException as exc:  # noqa: BLE001 - queremos capturar a corrida
            errors.append(exc)
        finally:
            conn.close()

    first = threading.Thread(target=claim, args=(_USER_A, _COMPANY_A))
    second = threading.Thread(target=claim, args=(_USER_B, _COMPANY_B))
    first.start()
    second.start()
    first.join()
    second.join()

    assert errors == []
    assert len(results) == 2
    check = _app_conn(pg, database, autocommit=False)
    try:
        check.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_A,))
        count_a = check.execute(
            "SELECT count(*) FROM user_verified_phones WHERE phone_e164 = %s",
            (_PHONE_A,),
        ).fetchone()
        check.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY_B,))
        count_b = check.execute(
            "SELECT count(*) FROM user_verified_phones WHERE phone_e164 = %s",
            (_PHONE_A,),
        ).fetchone()
        check.commit()
    finally:
        check.close()
    assert (int(count_a[0]), int(count_b[0])) in ((0, 1), (1, 0))
