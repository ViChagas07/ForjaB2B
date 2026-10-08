"""Vocabulario de estado do modulo invoicing (pure Python, sem frameworks)."""

from __future__ import annotations

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Situacao de uma fatura/duplicata."""

    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class InvoiceTerms(StrEnum):
    """Prazo de vencimento do boleto faturado."""

    NET_30 = "NET_30"  # vencimento em 30 dias
    NET_60 = "NET_60"  # vencimento em 60 dias
