"""Portas do contexto de credito (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class CreditAccountView:
    """Visao da conta de credito (limite + utilizado + disponivel)."""

    company_id: uuid.UUID
    credit_limit: Decimal
    used: Decimal
    available: Decimal
    currency: str


@dataclass(frozen=True, kw_only=True)
class CreditEntryView:
    """Lancamento do ledger (append-only)."""

    id: uuid.UUID
    entry_type: str
    amount: Decimal
    reference_type: str | None
    reference_id: uuid.UUID | None
    description: str | None
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class CreditOperationResult:
    """Resultado de uma operacao financeira (reserva/liberacao)."""

    entry_id: uuid.UUID
    entry_type: str
    amount: Decimal
    available: Decimal
    idempotent: bool


class CreditRepository(Protocol):
    """Persistencia do credito (ledger append-only + conta)."""

    async def get_account(self, company_id: uuid.UUID) -> CreditAccountView | None:
        """Consulta limite/utilizado/disponivel de uma empresa."""

    async def list_entries(self, company_id: uuid.UUID) -> list[CreditEntryView]:
        """Historico (ledger) de movimentacoes, em ordem cronologica."""

    async def reserve(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        idempotency_key: str,
        reference_type: str,
        reference_id: uuid.UUID,
        description: str | None,
    ) -> CreditOperationResult:
        """Reserva credito atomicamente (FOR UPDATE + valida saldo + ledger)."""

    async def release(
        self,
        *,
        company_id: uuid.UUID,
        amount: Decimal,
        idempotency_key: str,
        reference_type: str,
        reference_id: uuid.UUID,
        description: str | None,
    ) -> CreditOperationResult:
        """Libera uma reserva (reversao)."""
