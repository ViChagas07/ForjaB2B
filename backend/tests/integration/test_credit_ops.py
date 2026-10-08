"""Testes de integracao do dominio de credito (reserva/liberacao/idempotencia).

Usa empresas e contas de credito DEDICADAS (nao os seeds globais), inseridas com
contexto de tenant. Valida transacao, FOR UPDATE (concorrencia), idempotencia,
isolamento por empresa e precisao monetaria (Decimal).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.credit.application.errors import (
    CreditAccountNotFoundError,
    IdempotencyConflictError,
    InsufficientCreditError,
)
from app.modules.credit.infrastructure.repository import SqlAlchemyCreditRepository

from .conftest import PostgresInstance

_COMPANY_A = uuid.UUID("aaaa0000-0000-4000-8000-000000000001")
_COMPANY_B = uuid.UUID("bbbb0000-0000-4000-8000-000000000002")
_LIMIT = Decimal("1000.00")


@pytest.fixture()
def credit_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    """Empresas dedicadas + conta de credito RESETADA a cada teste (isolamento)."""
    conn = pg.connect_admin(autocommit=False)
    try:
        for company_id, cnpj, name in (
            (_COMPANY_A, "19999999000101", "Credit Empresa A"),
            (_COMPANY_B, "19999999000102", "Credit Empresa B"),
        ):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            conn.execute(
                "INSERT INTO companies (id, cnpj, legal_name, status) "
                "VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (company_id, cnpj, name),
            )
            # Reseta o estado de credito (ledger + conta) para o teste atual.
            conn.execute("DELETE FROM credit_entries WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM credit_accounts WHERE company_id = %s", (company_id,))
            conn.execute(
                "INSERT INTO credit_accounts (company_id, credit_limit) VALUES (%s, %s)",
                (company_id, _LIMIT),
            )
        conn.commit()
    finally:
        conn.close()


def _repo(uow_factory: SqlAlchemyUnitOfWorkFactory) -> SqlAlchemyCreditRepository:
    return SqlAlchemyCreditRepository(uow_factory)


async def test_saldo_disponivel_inicial(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    view = await _repo(uow_factory).get_account(_COMPANY_A)
    assert view is not None
    assert view.credit_limit == _LIMIT
    assert view.used == Decimal("0.00")
    assert view.available == _LIMIT


async def test_reserva_valida(uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None) -> None:
    result = await _repo(uow_factory).reserve(
        company_id=_COMPANY_A,
        amount=Decimal("250.00"),
        idempotency_key="res-a-1",
        reference_type="order",
        reference_id=uuid.uuid4(),
        description="pedido de teste",
    )
    assert result.entry_type == "RESERVE"
    assert result.available == Decimal("750.00")

    view = await _repo(uow_factory).get_account(_COMPANY_A)
    assert view is not None
    assert view.used == Decimal("250.00")
    assert view.available == Decimal("750.00")


async def test_reserva_acima_do_limite_rejeitada(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    repo = _repo(uow_factory)
    await repo.reserve(
        company_id=_COMPANY_A,
        amount=Decimal("900.00"),
        idempotency_key="res-a-over-1",
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    with pytest.raises(InsufficientCreditError):
        await repo.reserve(
            company_id=_COMPANY_A,
            amount=Decimal("100.01"),
            idempotency_key="res-a-over-2",
            reference_type="order",
            reference_id=uuid.uuid4(),
        )


async def test_liberacao_reverte_reserva(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    repo = _repo(uow_factory)
    await repo.reserve(
        company_id=_COMPANY_A,
        amount=Decimal("400.00"),
        idempotency_key="res-a-rel-1",
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    await repo.release(
        company_id=_COMPANY_A,
        amount=Decimal("400.00"),
        idempotency_key="rel-a-1",
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    view = await repo.get_account(_COMPANY_A)
    assert view is not None
    assert view.used == Decimal("0.00")
    assert view.available == _LIMIT


async def test_idempotencia_reserva_repetida(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    repo = _repo(uow_factory)
    key = "res-a-idem-1"
    first = await repo.reserve(
        company_id=_COMPANY_A,
        amount=Decimal("100.00"),
        idempotency_key=key,
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    second = await repo.reserve(
        company_id=_COMPANY_A,
        amount=Decimal("100.00"),
        idempotency_key=key,
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    assert second.entry_id == first.entry_id
    assert second.idempotent is True
    # Uma unica reserva no ledger (nao duplica).
    view = await repo.get_account(_COMPANY_A)
    assert view is not None
    assert view.used == Decimal("100.00")


async def test_idempotencia_payload_conflitante(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    repo = _repo(uow_factory)
    key = "res-a-conflict-1"
    await repo.reserve(
        company_id=_COMPANY_A,
        amount=Decimal("100.00"),
        idempotency_key=key,
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    with pytest.raises(IdempotencyConflictError):
        await repo.reserve(
            company_id=_COMPANY_A,
            amount=Decimal("200.00"),
            idempotency_key=key,
            reference_type="order",
            reference_id=uuid.uuid4(),
        )


async def test_conta_inexistente_404(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    from app.modules.credit.application.credit import GetCreditAccount

    use_case = GetCreditAccount(repository=_repo(uow_factory))
    with pytest.raises(CreditAccountNotFoundError):
        await use_case.get(uuid.uuid4())


async def test_isolamento_entre_empresas(
    uow_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    repo = _repo(uow_factory)
    await repo.reserve(
        company_id=_COMPANY_A,
        amount=Decimal("300.00"),
        idempotency_key="res-a-iso-1",
        reference_type="order",
        reference_id=uuid.uuid4(),
    )
    # Empresa B nao ve a exposicao nem o ledger de A.
    view_b = await repo.get_account(_COMPANY_B)
    assert view_b is not None
    assert view_b.used == Decimal("0.00")
    assert await repo.list_entries(_COMPANY_B) == []


@pytest.fixture()
async def concurrent_factory(app_database_url: str) -> AsyncIterator[SqlAlchemyUnitOfWorkFactory]:
    engine = create_async_engine(app_database_url, pool_size=4, max_overflow=0)
    try:
        yield SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    finally:
        await engine.dispose()


async def test_duas_reservas_concorrentes_nao_ultrapassam_limite(
    concurrent_factory: SqlAlchemyUnitOfWorkFactory, credit_seed: None
) -> None:
    """Duas reservas simultaneas de 600 (limite 1000): exatamente uma passa."""
    repo = _repo(concurrent_factory)

    async def reserve(tag: str) -> str:
        try:
            await repo.reserve(
                company_id=_COMPANY_A,
                amount=Decimal("600.00"),
                idempotency_key=f"res-a-conc-{tag}",
                reference_type="order",
                reference_id=uuid.uuid4(),
            )
            return "ok"
        except InsufficientCreditError:
            return "insufficient"

    results = await asyncio.gather(reserve("1"), reserve("2"))
    assert sorted(results) == ["insufficient", "ok"]

    view = await repo.get_account(_COMPANY_A)
    assert view is not None
    assert view.used == Decimal("600.00")
