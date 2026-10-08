"""Portas do contexto de faturamento (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.modules.invoicing.domain.enums import InvoiceTerms


@dataclass(frozen=True, kw_only=True)
class OrderForInvoice:
    """Pedido minimo necessario para faturar."""

    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    total: Decimal


@dataclass(frozen=True, kw_only=True)
class InvoiceView:
    """Visao de leitura de uma fatura (sem dados sensiveis)."""

    id: uuid.UUID
    order_id: uuid.UUID
    company_id: uuid.UUID
    number: str
    amount: Decimal
    status: str
    payment_terms: str
    currency: str
    due_at: datetime
    issued_at: datetime | None
    paid_at: datetime | None
    boleto_reference: str | None
    created_at: datetime


class InvoicingRepository(Protocol):
    """Persistencia de faturas + captura atomica de credito (tenant-scoped)."""

    async def get_order_for_invoice(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> OrderForInvoice | None:
        """Le o pedido a faturar (dentro do tenant do chamador)."""

    async def get_invoice_by_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> InvoiceView | None:
        """Consulta a fatura associada a um pedido."""

    async def get_invoice(self, company_id: uuid.UUID, invoice_id: uuid.UUID) -> InvoiceView | None:
        """Consulta uma fatura por id."""

    async def create_invoice(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: Decimal,
        terms: InvoiceTerms,
        issued_at: datetime,
    ) -> InvoiceView:
        """Cria a fatura e captura o credito (boleto) atomicamente."""
