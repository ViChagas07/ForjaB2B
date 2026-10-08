"""Regras de dominio do faturamento (pure Python, sem frameworks).

A fatura (invoice) vincula-se a um pedido ja faturado (boleto) e guarda o
vencimento conforme o termo (30/60 dias). Numero e referencia de boleto sao
deterministicos para garantir idempotencia sem integracao bancaria real.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from app.modules.invoicing.domain.enums import InvoiceTerms

_TERM_DAYS = {
    InvoiceTerms.NET_30: 30,
    InvoiceTerms.NET_60: 60,
}


def due_date(*, issued_at: datetime, terms: InvoiceTerms) -> datetime:
    """Vencimento = emissao + prazo do termo (30 ou 60 dias)."""
    return issued_at + timedelta(days=_TERM_DAYS[terms])


def invoice_number(order_id: uuid.UUID) -> str:
    """Numero deterministico e unico por pedido (uma fatura por pedido)."""
    return f"INV-{order_id}"


def boleto_reference(order_id: uuid.UUID) -> str:
    """Referencia simulada de boleto (sem integracao bancaria real)."""
    return f"BOLETO-{order_id}"
