"""Prova de integracao: Unit of Work SQLAlchemy + tenant context + RLS.

Valida contra PostgreSQL real (Testcontainers) que:
- o contexto de tenant e aplicado DENTRO da mesma transacao das consultas;
- o isolamento RLS funciona atraves da UoW (tenant A x tenant B);
- sem commit explicito, a UoW faz rollback (nada persiste);
- a reutilizacao de conexao do pool NAO herda o contexto anterior.

A tabela rls_probe_backend e FIXTURE exclusiva de teste (criada como
forja_admin), nao e dominio da aplicacao.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory

from .conftest import PostgresInstance

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_B = uuid.UUID("22222222-2222-2222-2222-222222222222")

_TABLE = "public.rls_probe_backend"


@pytest.fixture(scope="module")
def rls_probe_backend(pg: PostgresInstance) -> Iterator[None]:
    admin = pg.connect_admin()
    try:
        admin.execute(
            f"""
            CREATE TABLE {_TABLE} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                company_id UUID NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        admin.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
        admin.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
        admin.execute(
            f"""
            CREATE POLICY rls_probe_backend_all ON {_TABLE}
            USING (company_id = app.current_company_id())
            WITH CHECK (company_id = app.current_company_id())
            """
        )

        admin_tx = pg.connect_admin(autocommit=False)
        try:
            admin_tx.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
            admin_tx.execute(
                f"INSERT INTO {_TABLE} (company_id, payload) VALUES (%s, %s)",
                (TENANT_A, "alpha"),
            )
            admin_tx.commit()
            admin_tx.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_B, USER_B))
            admin_tx.execute(
                f"INSERT INTO {_TABLE} (company_id, payload) VALUES (%s, %s)",
                (TENANT_B, "beta"),
            )
            admin_tx.commit()
        finally:
            admin_tx.close()

        yield
    finally:
        admin.close()


async def _payloads(
    factory: SqlAlchemyUnitOfWorkFactory, tenant: TenantContext | None
) -> list[str]:
    async with factory.begin(tenant) as uow:
        result = await uow.session.execute(text(f"SELECT payload FROM {_TABLE} ORDER BY payload"))
        rows = [row[0] for row in result.all()]
        await uow.commit()
    return rows


async def test_uow_tenant_a_ve_apenas_proprias_linhas(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    rows = await _payloads(uow_factory, TenantContext(company_id=TENANT_A, user_id=USER_A))
    assert rows == ["alpha"]


async def test_uow_tenant_b_ve_apenas_proprias_linhas(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    rows = await _payloads(uow_factory, TenantContext(company_id=TENANT_B, user_id=USER_B))
    assert rows == ["beta"]


async def test_uow_sem_contexto_nao_ve_linhas(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    rows = await _payloads(uow_factory, None)
    assert rows == []


async def test_uow_contexto_definido_na_mesma_transacao(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    """As GUCs refletem o tenant dentro da transacao aberta pela UoW."""
    async with uow_factory.begin(TenantContext(company_id=TENANT_A, user_id=USER_A)) as uow:
        row = (
            await uow.session.execute(
                text("SELECT app.current_company_id(), app.current_user_id()")
            )
        ).one()
        assert row == (TENANT_A, USER_A)
        await uow.commit()


async def test_uow_insert_cross_tenant_negado(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    async with uow_factory.begin(TenantContext(company_id=TENANT_A, user_id=USER_A)) as uow:
        with pytest.raises(DBAPIError):
            await uow.session.execute(
                text(f"INSERT INTO {_TABLE} (company_id, payload) VALUES (:company, :payload)"),
                {"company": str(TENANT_B), "payload": "fraude"},
            )


async def test_uow_sem_commit_faz_rollback(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    tenant = TenantContext(company_id=TENANT_A, user_id=USER_A)
    async with uow_factory.begin(tenant) as uow:
        await uow.session.execute(
            text(f"INSERT INTO {_TABLE} (company_id, payload) VALUES (:company, :payload)"),
            {"company": str(TENANT_A), "payload": "sem-commit"},
        )
        # Sem commit(): __aexit__ deve fazer rollback.

    rows = await _payloads(uow_factory, tenant)
    assert "sem-commit" not in rows


async def test_pool_reuse_nao_herda_contexto_de_tenant(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    """Transacao A (tenant A) -> commit -> conexao ao pool -> transacao B.

    A engine da fixture tem pool_size=1: a segunda UoW reutiliza a mesma
    conexao fisica. O contexto de A nao pode sobreviver.
    """
    async with uow_factory.begin(TenantContext(company_id=TENANT_A, user_id=USER_A)) as uow:
        row = (await uow.session.execute(text("SELECT app.current_company_id()"))).scalar_one()
        assert row == TENANT_A
        await uow.commit()

    async with uow_factory.begin() as uow:
        row = (
            await uow.session.execute(
                text("SELECT app.current_company_id(), app.current_user_id()")
            )
        ).one()
        assert row == (None, None)
        await uow.commit()

    async with uow_factory.begin(TenantContext(company_id=TENANT_B)) as uow:
        rows = (
            await uow.session.execute(text(f"SELECT payload FROM {_TABLE} ORDER BY payload"))
        ).all()
        assert [r[0] for r in rows] == ["beta"]
        await uow.commit()


async def test_uow_excecao_dispara_rollback(
    uow_factory: SqlAlchemyUnitOfWorkFactory, rls_probe_backend: None
) -> None:
    tenant = TenantContext(company_id=TENANT_A, user_id=USER_A)
    with pytest.raises(RuntimeError, match="falha-simulada"):
        async with uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                text(f"INSERT INTO {_TABLE} (company_id, payload) VALUES (:company, :payload)"),
                {"company": str(TENANT_A), "payload": "com-excecao"},
            )
            raise RuntimeError("falha-simulada")

    rows = await _payloads(uow_factory, tenant)
    assert "com-excecao" not in rows
