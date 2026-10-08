"""Repositorio SQLAlchemy do contexto de faturamento.

``create_invoice`` cria a fatura e captura o credito na MESMA transacao:

1. ``RELEASE`` da reserva feita no pedido (boleto);
2. ``INVOICE_CAPTURE`` do mesmo valor, referenciando a fatura.

Como o ledger e append-only e RESERVE/INVOICE_CAPTURE somam exposicao, a
captura e uma conversao net-zero (nao duplica movimentacao de credito). A
idempotencia e garantida pelo numero deterministico da fatura (``INV-<order>``)
e pelas ``idempotency_key`` unicas dos lancamentos de credito.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.invoicing.application.errors import (
    InsufficientCreditError,
    OrderNotInvoiceableError,
)
from app.modules.invoicing.application.ports import (
    InvoiceView,
    OrderForInvoice,
)
from app.modules.invoicing.domain.enums import InvoiceTerms
from app.modules.invoicing.domain.invoice import boleto_reference, due_date, invoice_number

_INVOICES_NUMBER_UNIQUE = "uq_invoices_number"

_GET_ORDER = text(
    "SELECT id, company_id, status, total FROM orders "
    "WHERE id = :order_id AND company_id = :company_id"
)
_SELECT_INVOICE_BY_ORDER = text(
    "SELECT id, order_id, company_id, number, amount, status, payment_terms, currency, "
    "due_at, issued_at, paid_at, boleto_reference, created_at FROM invoices "
    "WHERE order_id = :order_id AND company_id = :company_id"
)
_SELECT_INVOICE_BY_ID = text(
    "SELECT id, order_id, company_id, number, amount, status, payment_terms, currency, "
    "due_at, issued_at, paid_at, boleto_reference, created_at FROM invoices "
    "WHERE id = :invoice_id AND company_id = :company_id"
)
_LOCK_CREDIT = text(
    "SELECT credit_limit FROM credit_accounts WHERE company_id = :company_id FOR UPDATE"
)
_SELECT_RESERVE = text(
    "SELECT COALESCE(SUM(CASE entry_type "
    "WHEN 'RESERVE' THEN amount "
    "WHEN 'RELEASE' THEN -amount "
    "ELSE 0 END), 0) FROM credit_entries "
    "WHERE reference_type = 'order' AND reference_id = :order_id "
    "AND entry_type IN ('RESERVE', 'RELEASE')"
)
_INSERT_CREDIT = text(
    "INSERT INTO credit_entries (credit_account_id, company_id, entry_type, amount, "
    "reference_type, reference_id, idempotency_key) "
    "VALUES (:company_id, :company_id, :entry_type, :amount, :reference_type, "
    ":reference_id, :key)"
)
_INSERT_INVOICE = text(
    "INSERT INTO invoices (order_id, company_id, number, amount, status, payment_terms, "
    "currency, due_at, issued_at, boleto_reference) "
    "VALUES (:order_id, :company_id, :number, :amount, 'PENDING', :payment_terms, "
    "'BRL', :due_at, :issued_at, :boleto_reference) RETURNING id"
)
_UPDATE_ORDER_STATUS = text(
    "UPDATE orders SET status = 'INVOICED' WHERE id = :order_id AND company_id = :company_id"
)


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    while current is not None:
        name = getattr(current, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        current = current.__cause__
    return ""


class SqlAlchemyInvoicingRepository:
    """Implementacao da porta InvoicingRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_order_for_invoice(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> OrderForInvoice | None:
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
            return OrderForInvoice(
                id=row.id, company_id=row.company_id, status=row.status, total=row.total
            )

    async def get_invoice_by_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> InvoiceView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_INVOICE_BY_ORDER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            await uow.commit()
            return None if row is None else self._to_view(row)

    async def get_invoice(self, company_id: uuid.UUID, invoice_id: uuid.UUID) -> InvoiceView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_INVOICE_BY_ID, {"invoice_id": invoice_id, "company_id": company_id}
                )
            ).first()
            await uow.commit()
            return None if row is None else self._to_view(row)

    async def create_invoice(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: Decimal,
        terms: InvoiceTerms,
        issued_at: datetime,
    ) -> InvoiceView:
        try:
            return await self._create_inner(
                company_id=company_id,
                order_id=order_id,
                amount=amount,
                terms=terms,
                issued_at=issued_at,
            )
        except Exception as exc:
            if _constraint_name(exc) == _INVOICES_NUMBER_UNIQUE:
                existing = await self.get_invoice_by_order(company_id, order_id)
                if existing is not None:
                    return existing
            raise

    async def _create_inner(
        self,
        *,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        amount: Decimal,
        terms: InvoiceTerms,
        issued_at: datetime,
    ) -> InvoiceView:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            # 1. Idempotencia (backstop para retries concorrentes).
            existing = (
                await uow.session.execute(
                    _SELECT_INVOICE_BY_ORDER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            if existing is not None:
                await uow.commit()
                return self._to_view(existing)

            # 2. Serializa a captura por empresa (FOR UPDATE na conta).
            account = (await uow.session.execute(_LOCK_CREDIT, {"company_id": company_id})).first()
            if account is None:  # pragma: no cover - conta sempre existe (seed)
                raise OrderNotInvoiceableError()

            # 3. Reserva existente do pedido (boleto). PIX nao reserva.
            reserved = Decimal(
                (await uow.session.execute(_SELECT_RESERVE, {"order_id": order_id})).scalar_one()
            )
            if reserved <= 0:
                raise OrderNotInvoiceableError()
            if reserved < amount:
                raise InsufficientCreditError()

            # 4. Gera a fatura (numero deterministico para idempotencia).
            number = invoice_number(order_id)
            invoice_id = (
                await uow.session.execute(
                    _INSERT_INVOICE,
                    {
                        "order_id": order_id,
                        "company_id": company_id,
                        "number": number,
                        "amount": amount,
                        "payment_terms": terms.value,
                        "due_at": due_date(issued_at=issued_at, terms=terms),
                        "issued_at": issued_at,
                        "boleto_reference": boleto_reference(order_id),
                    },
                )
            ).scalar_one()

            # 5. Captura: converte a reserva em divida faturada (net-zero).
            await uow.session.execute(
                _INSERT_CREDIT,
                {
                    "company_id": company_id,
                    "entry_type": "RELEASE",
                    "amount": reserved,
                    "reference_type": "order",
                    "reference_id": order_id,
                    "key": f"invoice_release:{order_id}",
                },
            )
            await uow.session.execute(
                _INSERT_CREDIT,
                {
                    "company_id": company_id,
                    "entry_type": "INVOICE_CAPTURE",
                    "amount": reserved,
                    "reference_type": "invoice",
                    "reference_id": invoice_id,
                    "key": f"invoice_capture:{order_id}",
                },
            )

            # 6. Avanca o pedido para INVOICED.
            await uow.session.execute(
                _UPDATE_ORDER_STATUS, {"order_id": order_id, "company_id": company_id}
            )
            await uow.commit()

        result = await self.get_invoice(company_id, invoice_id)
        if result is None:  # pragma: no cover - fatura acabou de ser criada
            raise OrderNotInvoiceableError()
        return result

    @staticmethod
    def _to_view(row: Any) -> InvoiceView:
        return InvoiceView(
            id=row.id,
            order_id=row.order_id,
            company_id=row.company_id,
            number=row.number,
            amount=row.amount,
            status=row.status,
            payment_terms=row.payment_terms,
            currency=row.currency,
            due_at=row.due_at,
            issued_at=row.issued_at,
            paid_at=row.paid_at,
            boleto_reference=row.boleto_reference,
            created_at=row.created_at,
        )
