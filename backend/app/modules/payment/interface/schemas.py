"""Schemas HTTP do contexto de pagamento."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payment.domain.enums import PaymentMethod


class WebhookEventType(StrEnum):
    """Tipos de evento aceitos pelo webhook do provedor."""

    PAYMENT_PAID = "payment.paid"
    PAYMENT_FAILED = "payment.failed"


class InitiatePaymentRequest(BaseModel):
    """Entrada de iniciacao de pagamento (o pedido ja deve existir)."""

    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    method: PaymentMethod
    idempotency_key: str = Field(min_length=1, max_length=64)


class PaymentResponse(BaseModel):
    """Visao publica de um pagamento (sem dados sensiveis)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    company_id: uuid.UUID
    order_id: uuid.UUID
    invoice_id: uuid.UUID | None
    method: str
    amount: Decimal
    discount_amount: Decimal
    status: str
    provider: str
    provider_reference: str
    created_at: datetime
    paid_at: datetime | None


class WebhookEventRequest(BaseModel):
    """Evento do provedor de pagamento (payload assinado por HMAC)."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    event_id: str = Field(min_length=1, max_length=128)
    event_type: WebhookEventType
    provider_reference: str
    company_id: uuid.UUID


class WebhookResponse(BaseModel):
    """Resultado do processamento de um evento de webhook."""

    model_config = ConfigDict(extra="forbid")

    outcome: str
    payment_id: uuid.UUID
    status: str
