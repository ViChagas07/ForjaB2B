"""Portas do contexto de pagamento (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.modules.payment.domain.enums import PaymentMethod, PaymentStatus


@dataclass(frozen=True, kw_only=True)
class OrderForPayment:
    """Pedido minimo necessario para iniciar um pagamento."""

    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    total: Decimal


@dataclass(frozen=True, kw_only=True)
class InvoiceForPayment:
    """Fatura minima necessaria para quitar um boleto."""

    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    amount: Decimal


@dataclass(frozen=True, kw_only=True)
class GatewayInstruction:
    """Instrucao devolvida pelo gateway (Fake) para o pagador."""

    provider: str
    provider_reference: str


@dataclass(frozen=True, kw_only=True)
class PaymentView:
    """Visao de leitura de um pagamento (sem dados sensiveis)."""

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


@dataclass(frozen=True, kw_only=True)
class PaymentResult:
    """Resultado do processamento de um evento de webhook."""

    payment: PaymentView
    outcome: str  # PaymentEventOutcome.value


class PaymentRepository(Protocol):
    """Persistencia de pagamentos + aplicacao atomica de eventos de webhook."""

    async def get_order_for_payment(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> OrderForPayment | None:
        """Le o pedido a pagar (dentro do tenant do chamador)."""

    async def get_invoice_by_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> InvoiceForPayment | None:
        """Le a fatura associada a um pedido (para quitar boleto)."""

    async def get_payment(self, company_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentView | None:
        """Consulta um pagamento por id."""

    async def create_payment(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        invoice_id: uuid.UUID | None,
        method: PaymentMethod,
        amount: Decimal,
        discount_amount: Decimal,
        provider: str,
        provider_reference: str,
        idempotency_key: str,
    ) -> PaymentView:
        """Cria um pagamento PENDING (idempotente por idempotency_key)."""

    async def confirm_event(
        self,
        *,
        company_id: uuid.UUID,
        provider_reference: str,
        provider: str,
        event_id: str,
        target_status: PaymentStatus,
        occurred_at: datetime,
    ) -> PaymentResult:
        """Aplica um evento de webhook (idempotente, com maquina de estados)."""


class PaymentGateway(Protocol):
    """Porta do provedor de pagamento (Fake/local por padrao)."""

    async def initiate(
        self, *, method: PaymentMethod, amount: Decimal, order_id: uuid.UUID
    ) -> GatewayInstruction:
        """Cria a intencao de pagamento e devolve a referencia do provedor."""
