"""Casos de uso do contexto de faturamento.

A fatura e criada para pedidos faturados (boleto): captura o credito ja
reservado no pedido (RELEASE da reserva + INVOICE_CAPTURE), de forma atomica e
idempotente. Pedidos PIX (sem reserva) nao sao fataveis.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.modules.invoicing.application.errors import (
    IdempotencyConflictError,
    InvoiceNotFoundError,
    OrderNotFoundError,
    OrderNotInvoiceableError,
)
from app.modules.invoicing.application.ports import (
    InvoiceView,
    InvoicingRepository,
)
from app.modules.invoicing.domain.enums import InvoiceTerms

_INVOICEABLE_STATUSES = frozenset({"RECEIVED", "CREDIT_REVIEW"})


class CreateInvoice:
    """Caso de uso: cria a fatura de um pedido (boleto) e captura o credito."""

    def __init__(
        self,
        *,
        repository: InvoicingRepository,
        now: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or datetime.now(UTC)

    async def create(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        terms: InvoiceTerms = InvoiceTerms.NET_30,
    ) -> InvoiceView:
        order = await self._repository.get_order_for_invoice(company_id, order_id)
        if order is None:
            raise OrderNotFoundError()

        existing = await self._repository.get_invoice_by_order(company_id, order_id)
        if existing is not None:
            if existing.amount != order.total or existing.payment_terms != terms.value:
                raise IdempotencyConflictError()
            return existing

        if order.status not in _INVOICEABLE_STATUSES:
            raise OrderNotInvoiceableError()

        return await self._repository.create_invoice(
            company_id=company_id,
            order_id=order_id,
            amount=order.total,
            terms=terms,
            issued_at=self._now,
        )


class GetInvoice:
    """Caso de uso: consulta uma fatura por id."""

    def __init__(self, *, repository: InvoicingRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID, invoice_id: uuid.UUID) -> InvoiceView:
        invoice = await self._repository.get_invoice(company_id, invoice_id)
        if invoice is None:
            raise InvoiceNotFoundError()
        return invoice


class GetInvoiceByOrder:
    """Caso de uso: consulta a fatura associada a um pedido."""

    def __init__(self, *, repository: InvoicingRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID, order_id: uuid.UUID) -> InvoiceView:
        invoice = await self._repository.get_invoice_by_order(company_id, order_id)
        if invoice is None:
            raise InvoiceNotFoundError()
        return invoice
