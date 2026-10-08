"""Repositorio SQLAlchemy do contexto de credito (ledger append-only).

Operacoes que alteram credito sao transacionais e concorrencia-safe: a conta e
bloqueada com ``SELECT ... FOR UPDATE`` dentro da UoW (tenant context aplicado),
o saldo e validado na MESMA transacao (somatorio do ledger), e o lancamento e
registrado. Duas compras concorrentes nao ultrapassam o limite porque o lock na
linha da conta serializa as reservas da empresa.

Idempotencia: a ``idempotency_key`` e unica (constraint parcial do ledger). Com
o lock da conta adquirido, a checagem de chave existente e livre de corrida;
chave repetida com payload identico devolve o resultado existente, com payload
diferente levanta conflito.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.credit.application.errors import (
    CreditAccountNotFoundError,
    IdempotencyConflictError,
    InsufficientCreditError,
)
from app.modules.credit.application.ports import (
    CreditAccountView,
    CreditEntryView,
    CreditOperationResult,
)
from app.modules.credit.domain.ledger import LedgerEntry, available_credit, exposure

_LOCK_ACCOUNT = text(
    "SELECT credit_limit, currency FROM credit_accounts WHERE company_id = :company_id FOR UPDATE"
)
_READ_ACCOUNT = text(
    "SELECT credit_limit, currency FROM credit_accounts WHERE company_id = :company_id"
)
_SELECT_ENTRIES = text(
    "SELECT entry_type, amount FROM credit_entries WHERE company_id = :company_id "
    "ORDER BY created_at, id"
)
_SELECT_ENTRIES_FULL = text(
    "SELECT id, entry_type, amount, reference_type, reference_id, description, created_at "
    "FROM credit_entries WHERE company_id = :company_id ORDER BY created_at, id"
)
_SELECT_BY_KEY = text(
    "SELECT id, entry_type, amount FROM credit_entries WHERE idempotency_key = :idempotency_key"
)
_INSERT_ENTRY = text(
    "INSERT INTO credit_entries "
    "(credit_account_id, company_id, entry_type, amount, reference_type, reference_id, "
    " idempotency_key, description) "
    "VALUES (:company_id, :company_id, :entry_type, :amount, :reference_type, :reference_id, "
    " :idempotency_key, :description) "
    "RETURNING id"
)


def _to_ledger(rows: Iterable[Any]) -> list[LedgerEntry]:
    return [LedgerEntry(entry_type=entry_type, amount=amount) for entry_type, amount in rows]


class SqlAlchemyCreditRepository:
    """Implementacao da porta CreditRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_account(self, company_id: uuid.UUID) -> CreditAccountView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            account = (await uow.session.execute(_READ_ACCOUNT, {"company_id": company_id})).first()
            if account is None:
                await uow.commit()
                return None
            entries = (await uow.session.execute(_SELECT_ENTRIES, {"company_id": company_id})).all()
            await uow.commit()
            credit_limit, currency = account
            used = exposure(_to_ledger(entries))
            return CreditAccountView(
                company_id=company_id,
                credit_limit=credit_limit,
                used=used,
                available=credit_limit - used,
                currency=currency,
            )

    async def list_entries(self, company_id: uuid.UUID) -> list[CreditEntryView]:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            rows = (
                await uow.session.execute(_SELECT_ENTRIES_FULL, {"company_id": company_id})
            ).all()
            await uow.commit()
            return [
                CreditEntryView(
                    id=r.id,
                    entry_type=r.entry_type,
                    amount=r.amount,
                    reference_type=r.reference_type,
                    reference_id=r.reference_id,
                    description=r.description,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    async def reserve(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        idempotency_key: str,
        reference_type: str,
        reference_id: uuid.UUID,
        description: str | None = None,
    ) -> CreditOperationResult:
        return await self._apply_entry(
            company_id=company_id,
            amount=amount,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            entry_type="RESERVE",
            check_balance=True,
        )

    async def release(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        idempotency_key: str,
        reference_type: str,
        reference_id: uuid.UUID,
        description: str | None = None,
    ) -> CreditOperationResult:
        return await self._apply_entry(
            company_id=company_id,
            amount=amount,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            entry_type="RELEASE",
            check_balance=False,
        )

    async def _apply_entry(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        idempotency_key: str,
        reference_type: str,
        reference_id: uuid.UUID,
        description: str | None,
        entry_type: str,
        check_balance: bool,
    ) -> CreditOperationResult:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            # 1. Bloqueia a conta (serializa operacoes da empresa).
            account = (await uow.session.execute(_LOCK_ACCOUNT, {"company_id": company_id})).first()
            if account is None:
                raise CreditAccountNotFoundError()
            credit_limit = account[0]

            # 2. Idempotencia: chave ja usada? (sem corrida: lock adquirido).
            existing = (
                await uow.session.execute(_SELECT_BY_KEY, {"idempotency_key": idempotency_key})
            ).first()
            if existing is not None:
                existing_id, existing_type, existing_amount = existing
                if existing_type == entry_type and existing_amount == amount:
                    entries = (
                        await uow.session.execute(_SELECT_ENTRIES, {"company_id": company_id})
                    ).all()
                    await uow.commit()
                    available = available_credit(credit_limit, _to_ledger(entries))
                    return CreditOperationResult(
                        entry_id=existing_id,
                        entry_type=existing_type,
                        amount=existing_amount,
                        available=available,
                        idempotent=True,
                    )
                raise IdempotencyConflictError()

            # 3. Saldo dentro da mesma transacao (somatorio do ledger).
            if check_balance:
                entries = (
                    await uow.session.execute(_SELECT_ENTRIES, {"company_id": company_id})
                ).all()
                available = available_credit(credit_limit, _to_ledger(entries))
                if available < amount:
                    raise InsufficientCreditError()

            # 4. Registra o lancamento (append-only).
            entry_id = (
                await uow.session.execute(
                    _INSERT_ENTRY,
                    {
                        "company_id": company_id,
                        "entry_type": entry_type,
                        "amount": amount,
                        "reference_type": reference_type,
                        "reference_id": reference_id,
                        "idempotency_key": idempotency_key,
                        "description": description,
                    },
                )
            ).scalar_one()

            entries_after = (
                await uow.session.execute(_SELECT_ENTRIES, {"company_id": company_id})
            ).all()
            await uow.commit()
            available_after = available_credit(credit_limit, _to_ledger(entries_after))
            return CreditOperationResult(
                entry_id=entry_id,
                entry_type=entry_type,
                amount=amount,
                available=available_after,
                idempotent=False,
            )
