"""Testes unitarios do dominio de faturamento (numero e vencimento)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.modules.invoicing.domain.enums import InvoiceTerms
from app.modules.invoicing.domain.invoice import boleto_reference, due_date, invoice_number

_ORDER_ID = uuid.UUID("dddd0000-0000-4000-8000-000000000099")


def test_due_date_net_30() -> None:
    issued = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    assert due_date(issued_at=issued, terms=InvoiceTerms.NET_30) == datetime(
        2026, 11, 7, 12, 0, tzinfo=UTC
    )


def test_due_date_net_60() -> None:
    issued = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    assert due_date(issued_at=issued, terms=InvoiceTerms.NET_60) == datetime(
        2026, 12, 7, 12, 0, tzinfo=UTC
    )


def test_invoice_number_deterministico() -> None:
    assert invoice_number(_ORDER_ID) == f"INV-{_ORDER_ID}"
    assert invoice_number(_ORDER_ID) == invoice_number(_ORDER_ID)


def test_boleto_reference_deterministico() -> None:
    assert boleto_reference(_ORDER_ID) == f"BOLETO-{_ORDER_ID}"
