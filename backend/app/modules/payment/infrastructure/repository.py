"""Repositorio SQLAlchemy do contexto de pagamento.

``create_payment`` persiste um pagamento PENDING (idempotente por
``idempotency_key``). ``confirm_event`` aplica o evento do webhook ATOMICAMENTE:

1. bloqueia o pagamento (FOR UPDATE) serializando eventos concorrentes;
2. checa idempotencia pelo par (provider, event_id);
3. valida a transicao na maquina de estados (rejeitando transicoes invalidas);
4. aplica o novo estado e, para boleto pago, marca a fatura PAID e registra o
   lancamento ``PAYMENT`` no ledger de credito (reduzindo exposicao), tudo na
   mesma transacao, sem captura ou liberacao duplicada.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.outbox import enqueue_notification
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.payment.application.errors import (
    IdempotencyConflictError,
    PaymentNotFoundError,
)
from app.modules.payment.application.ports import (
    InvoiceForPayment,
    OrderForPayment,
    PaymentResult,
    PaymentView,
)
from app.modules.payment.domain.enums import (
    PaymentEventOutcome,
    PaymentMethod,
    PaymentStatus,
)
from app.modules.payment.domain.payment import can_transition

_GET_ORDER = text(
    "SELECT id, company_id, status, total FROM orders "
    "WHERE id = :order_id AND company_id = :company_id"
)
_GET_INVOICE_BY_ORDER = text(
    "SELECT id, company_id, status, amount FROM invoices "
    "WHERE order_id = :order_id AND company_id = :company_id"
)
_SELECT_PAYMENT = text(
    "SELECT id, company_id, order_id, invoice_id, method, amount, discount_amount, "
    "status, provider, provider_reference, created_at, paid_at FROM payments "
    "WHERE id = :payment_id AND company_id = :company_id"
)
_SELECT_PAYMENT_BY_KEY = text("SELECT id FROM payments WHERE idempotency_key = :idempotency_key")
_LOCK_PAYMENT_BY_REFERENCE = text(
    "SELECT id, company_id, order_id, invoice_id, method, amount, discount_amount, "
    "status, provider, provider_reference, created_at, paid_at FROM payments "
    "WHERE provider_reference = :ref AND company_id = :company_id FOR UPDATE"
)
_INSERT_PAYMENT = text(
    "INSERT INTO payments (company_id, order_id, invoice_id, method, amount, "
    "discount_amount, status, provider, provider_reference, idempotency_key) "
    "VALUES (:company_id, :order_id, :invoice_id, :method, :amount, :discount_amount, "
    "'PENDING', :provider, :provider_reference, :idempotency_key) RETURNING id"
)
_SELECT_EVENT = text(
    "SELECT id FROM payment_events WHERE provider = :provider AND event_id = :event_id"
)
_INSERT_EVENT = text(
    "INSERT INTO payment_events (company_id, payment_id, provider, event_id, event_type, "
    "outcome) VALUES (:company_id, :payment_id, :provider, :event_id, :event_type, :outcome)"
)
_UPDATE_PAYMENT_STATUS = text(
    "UPDATE payments SET status = :status, paid_at = :paid_at, failed_at = :failed_at, "
    "updated_at = now() WHERE id = :payment_id AND company_id = :company_id"
)
_UPDATE_INVOICE_PAID = text(
    "UPDATE invoices SET status = 'PAID', paid_at = :paid_at, updated_at = now() "
    "WHERE id = :invoice_id AND company_id = :company_id"
)
_INSERT_CREDIT = text(
    "INSERT INTO credit_entries (credit_account_id, company_id, entry_type, amount, "
    "reference_type, reference_id, idempotency_key) "
    "VALUES (:company_id, :company_id, 'PAYMENT', :amount, 'payment', :payment_id, :key)"
)

_PAYMENTS_KEY_UNIQUE = "uq_payments_idempotency_key"


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    while current is not None:
        name = getattr(current, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        current = current.__cause__
    return ""


def _to_view(row: Any) -> PaymentView:
    return PaymentView(
        id=row.id,
        company_id=row.company_id,
        order_id=row.order_id,
        invoice_id=row.invoice_id,
        method=row.method,
        amount=row.amount,
        discount_amount=row.discount_amount,
        status=row.status,
        provider=row.provider,
        provider_reference=row.provider_reference,
        created_at=row.created_at,
        paid_at=row.paid_at,
    )


class SqlAlchemyPaymentRepository:
    """Implementacao da porta PaymentRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_order_for_payment(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> OrderForPayment | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _GET_ORDER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            await uow.commit()
            if row is None:
                return None
            return OrderForPayment(
                id=row.id, company_id=row.company_id, status=row.status, total=row.total
            )

    async def get_invoice_by_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> InvoiceForPayment | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _GET_INVOICE_BY_ORDER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            await uow.commit()
            if row is None:
                return None
            return InvoiceForPayment(
                id=row.id, company_id=row.company_id, status=row.status, amount=row.amount
            )

    async def get_payment(self, company_id: uuid.UUID, payment_id: uuid.UUID) -> PaymentView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_PAYMENT, {"payment_id": payment_id, "company_id": company_id}
                )
            ).first()
            await uow.commit()
            return None if row is None else _to_view(row)

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
        try:
            return await self._create_inner(
                company_id=company_id,
                order_id=order_id,
                invoice_id=invoice_id,
                method=method,
                amount=amount,
                discount_amount=discount_amount,
                provider=provider,
                provider_reference=provider_reference,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            if _constraint_name(exc) == _PAYMENTS_KEY_UNIQUE:
                existing = await self._find_by_key(company_id, idempotency_key)
                if existing is not None:
                    return await self._idempotent_or_conflict(existing, company_id, method, amount)
            raise

    async def _create_inner(
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
        existing = await self._find_by_key(company_id, idempotency_key)
        if existing is not None:
            return await self._idempotent_or_conflict(existing, company_id, method, amount)

        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            payment_id = (
                await uow.session.execute(
                    _INSERT_PAYMENT,
                    {
                        "company_id": company_id,
                        "order_id": order_id,
                        "invoice_id": invoice_id,
                        "method": method.value,
                        "amount": amount,
                        "discount_amount": discount_amount,
                        "provider": provider,
                        "provider_reference": provider_reference,
                        "idempotency_key": idempotency_key,
                    },
                )
            ).scalar_one()
            await uow.commit()

        result = await self.get_payment(company_id, payment_id)
        if result is None:  # pragma: no cover - pagamento acabou de ser criado
            raise PaymentNotFoundError()
        return result

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
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _LOCK_PAYMENT_BY_REFERENCE,
                    {"ref": provider_reference, "company_id": company_id},
                )
            ).first()
            if row is None:
                raise PaymentNotFoundError()
            payment = _to_view(row)

            # Idempotencia: evento ja processado?
            existing = (
                await uow.session.execute(
                    _SELECT_EVENT, {"provider": provider, "event_id": event_id}
                )
            ).first()
            if existing is not None:
                await uow.commit()
                return PaymentResult(payment=payment, outcome=PaymentEventOutcome.DUPLICATE.value)

            # Maquina de estados: rejeita transicoes invalidas (fora de ordem).
            if not can_transition(PaymentStatus(payment.status), target_status):
                await uow.session.execute(
                    _INSERT_EVENT,
                    {
                        "company_id": company_id,
                        "payment_id": payment.id,
                        "provider": provider,
                        "event_id": event_id,
                        "event_type": target_status.value,
                        "outcome": PaymentEventOutcome.REJECTED.value,
                    },
                )
                await uow.commit()
                return PaymentResult(payment=payment, outcome=PaymentEventOutcome.REJECTED.value)

            paid_at = occurred_at if target_status == PaymentStatus.PAID else None
            failed_at = occurred_at if target_status == PaymentStatus.FAILED else None
            await uow.session.execute(
                _UPDATE_PAYMENT_STATUS,
                {
                    "payment_id": payment.id,
                    "company_id": company_id,
                    "status": target_status.value,
                    "paid_at": paid_at,
                    "failed_at": failed_at,
                },
            )

            # Boleto pago quita a fatura e reduz a exposicao no ledger (PAYMENT).
            if payment.method == PaymentMethod.BOLETO.value and target_status == PaymentStatus.PAID:
                await uow.session.execute(
                    _UPDATE_INVOICE_PAID,
                    {
                        "invoice_id": payment.invoice_id,
                        "paid_at": paid_at,
                        "company_id": company_id,
                    },
                )
                await uow.session.execute(
                    _INSERT_CREDIT,
                    {
                        "company_id": company_id,
                        "amount": payment.amount,
                        "payment_id": payment.id,
                        "key": f"payment:{payment.id}",
                    },
                )

            await uow.session.execute(
                _INSERT_EVENT,
                {
                    "company_id": company_id,
                    "payment_id": payment.id,
                    "provider": provider,
                    "event_id": event_id,
                    "event_type": target_status.value,
                    "outcome": PaymentEventOutcome.APPLIED.value,
                },
            )

            # Outbox: pagamento confirmado publica notificacao na mesma transacao.
            if target_status == PaymentStatus.PAID:
                await enqueue_notification(
                    uow.session,
                    company_id=company_id,
                    event_type="payment.confirmed",
                    aggregate_id=payment.order_id,
                )

            await uow.commit()

        result = await self.get_payment(company_id, payment.id)
        if result is None:  # pragma: no cover - pagamento acabou de ser atualizado
            raise PaymentNotFoundError()
        return PaymentResult(payment=result, outcome=PaymentEventOutcome.APPLIED.value)

    async def _find_by_key(self, company_id: uuid.UUID, idempotency_key: str) -> uuid.UUID | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_PAYMENT_BY_KEY, {"idempotency_key": idempotency_key}
                )
            ).first()
            await uow.commit()
            return row[0] if row is not None else None

    async def _idempotent_or_conflict(
        self,
        payment_id: uuid.UUID,
        company_id: uuid.UUID,
        method: PaymentMethod,
        expected_amount: Decimal,
    ) -> PaymentView:
        payment = await self.get_payment(company_id, payment_id)
        if payment is None:
            raise IdempotencyConflictError()
        if payment.method != method.value or payment.amount != expected_amount:
            raise IdempotencyConflictError()
        return payment
