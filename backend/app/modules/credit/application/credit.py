"""Casos de uso do contexto de credito (consulta e operacoes transacionais)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.modules.credit.application.errors import CreditAccountNotFoundError
from app.modules.credit.application.ports import (
    CreditAccountView,
    CreditEntryView,
    CreditOperationResult,
    CreditRepository,
)


class GetCreditAccount:
    def __init__(self, *, repository: CreditRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID) -> CreditAccountView:
        account = await self._repository.get_account(company_id)
        if account is None:
            raise CreditAccountNotFoundError()
        return account


class ListCreditEntries:
    def __init__(self, *, repository: CreditRepository) -> None:
        self._repository = repository

    async def list(self, company_id: uuid.UUID) -> list[CreditEntryView]:
        return await self._repository.list_entries(company_id)


class ReserveCredit:
    def __init__(self, *, repository: CreditRepository) -> None:
        self._repository = repository

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
        return await self._repository.reserve(
            company_id=company_id,
            amount=amount,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )


class ReleaseCredit:
    def __init__(self, *, repository: CreditRepository) -> None:
        self._repository = repository

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
        return await self._repository.release(
            company_id=company_id,
            amount=amount,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )
