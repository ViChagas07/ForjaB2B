"""Schemas HTTP do contexto de faturamento."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.modules.invoicing.domain.enums import InvoiceTerms


class CreateInvoiceRequest(BaseModel):
    """Entrada de criacao de fatura (o pedido ja deve estar reservado)."""

    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    payment_terms: InvoiceTerms = InvoiceTerms.NET_30


class InvoiceResponse(BaseModel):
    """Visao publica de uma fatura (sem dados sensiveis)."""

    model_config = ConfigDict(extra="forbid")

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
