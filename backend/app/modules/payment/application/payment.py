"""Casos de uso do contexto de pagamento.

- ``InitiatePayment`` cria um pagamento PENDING via gateway (Fake), calculando
  o desconto PIX no backend e o valor a pagar em ``Decimal``.
- ``ConfirmPayment`` aplica eventos de webhook (pagamento confirmado/falhou) de
  forma idempotente e com maquina de estados; a integracao com fatura e ledger
  de credito (boleto) acontece na infraestrutura, atomicamente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.payment.application.errors import (
    InvoiceNotFoundError,
    InvoiceNotPayableError,
    OrderNotFoundError,
    OrderNotPayableError,
    PaymentNotFoundError,
    PaymentNotRefundableError,
)
from app.modules.payment.application.ports import (
    GatewayInstruction,
    PaymentGateway,
    PaymentRefundGateway,
    PaymentRepository,
    PaymentResult,
    PaymentView,
)
from app.modules.payment.domain.enums import PaymentMethod, PaymentStatus
from app.modules.payment.domain.payment import payable_amount, pix_discount_amount

_PAYABLE_ORDER_STATUSES = frozenset({"RECEIVED", "CREDIT_REVIEW"})

_ZERO = Decimal("0.00")


class InitiatePayment:
    """Caso de uso: inicia um pagamento (PIX/CARD a vista ou BOLETO de fatura)."""

    def __init__(
        self,
        *,
        repository: PaymentRepository,
        gateway: PaymentGateway,
        pix_discount_rate: Decimal,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._pix_discount_rate = pix_discount_rate

    async def initiate(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        method: PaymentMethod,
        idempotency_key: str,
        locale: str = "pt-BR",
    ) -> PaymentView:
        order = await self._repository.get_order_for_payment(company_id, order_id)
        if order is None:
            raise OrderNotFoundError()

        invoice_id: uuid.UUID | None = None
        discount_amount = _ZERO
        if method == PaymentMethod.BOLETO:
            invoice = await self._repository.get_invoice_by_order(company_id, order_id)
            if invoice is None:
                raise InvoiceNotFoundError()
            if invoice.status != "PENDING":
                raise InvoiceNotPayableError()
            amount = invoice.amount
            invoice_id = invoice.id
        else:
            if order.status not in _PAYABLE_ORDER_STATUSES:
                raise OrderNotPayableError()
            if method == PaymentMethod.PIX:
                discount_amount = pix_discount_amount(order.total, self._pix_discount_rate)
            amount = payable_amount(order.total, discount_amount)

        instruction: GatewayInstruction = await self._gateway.initiate(
            method=method,
            amount=amount,
            currency=order.currency,
            order_id=order_id,
            company_id=company_id,
            locale=locale,
        )
        view = await self._repository.create_payment(
            company_id=company_id,
            order_id=order_id,
            invoice_id=invoice_id,
            method=method,
            amount=amount,
            discount_amount=discount_amount,
            provider=instruction.provider,
            provider_reference=instruction.provider_reference,
            idempotency_key=idempotency_key,
        )
        if instruction.checkout_url is None:
            return view
        return replace(view, checkout_url=instruction.checkout_url)


class ConfirmPayment:
    """Caso de uso: processa um evento de webhook do provedor."""

    def __init__(self, *, repository: PaymentRepository, now: datetime | None = None) -> None:
        self._repository = repository
        self._now = now or datetime.now(UTC)

    async def confirm(
        self,
        *,
        company_id: uuid.UUID,
        provider_reference: str,
        provider: str,
        event_id: str,
        target_status: PaymentStatus,
    ) -> PaymentResult:
        return await self._repository.confirm_event(
            company_id=company_id,
            provider_reference=provider_reference,
            provider=provider,
            event_id=event_id,
            target_status=target_status,
            occurred_at=self._now,
        )


class GetPayment:
    """Caso de uso: consulta um pagamento por id."""

    def __init__(self, *, repository: PaymentRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentView:
        payment = await self._repository.get_payment(company_id, payment_id)
        if payment is None:
            raise PaymentNotFoundError()
        return payment


class RefundPayment:
    """Estorna integralmente um pagamento Stripe PAID."""

    def __init__(self, *, repository: PaymentRepository, gateway: PaymentRefundGateway) -> None:
        self._repository = repository
        self._gateway = gateway

    async def refund(self, company_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentView:
        payment = await self._repository.get_payment(company_id, payment_id)
        if payment is None:
            raise PaymentNotFoundError()
        if payment.status != PaymentStatus.PAID.value or payment.provider != "STRIPE":
            raise PaymentNotRefundableError()

        await self._gateway.refund(provider_reference=payment.provider_reference)
        return await self._repository.refund_payment(company_id, payment_id)


@dataclass(frozen=True, kw_only=True)
class ReconcileReport:
    """Resumo da conciliacao de sessoes Stripe PENDING."""

    checked: int
    applied: int
    skipped: int


class ReconcileStripePayments:
    """Reconcilia pagamentos Stripe PENDING consultando a sessao no provedor.

    Cobre webhooks perdidos: se a sessao remota esta paga, confirma; se expirou,
    cancela. Usa o mesmo ``ConfirmPayment`` (idempotencia e transicoes atomicas).
    """

    def __init__(self, *, repository: PaymentRepository, gateway: PaymentRefundGateway) -> None:
        self._repository = repository
        self._gateway = gateway
        self._confirm = ConfirmPayment(repository=repository)

    async def run(self, company_id: uuid.UUID, limit: int = 50) -> ReconcileReport:
        pending = await self._repository.list_pending_stripe(company_id, limit)
        applied = 0
        skipped = 0
        for _payment_id, provider_reference in pending:
            remote = await self._gateway.retrieve_status(provider_reference=provider_reference)
            if remote == "paid":
                target = PaymentStatus.PAID
            elif remote == "expired":
                target = PaymentStatus.CANCELLED
            else:
                skipped += 1
                continue

            result = await self._confirm.confirm(
                company_id=company_id,
                provider_reference=provider_reference,
                provider="STRIPE",
                event_id=f"reconcile:{provider_reference}:{target.value}",
                target_status=target,
            )
            if result.outcome == "APPLIED":
                applied += 1
            else:
                skipped += 1

        return ReconcileReport(checked=len(pending), applied=applied, skipped=skipped)
