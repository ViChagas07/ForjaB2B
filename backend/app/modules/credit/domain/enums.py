"""Vocabulario de estado do modulo credit (pure Python, sem frameworks).

O ledger de credito e append-only: os tipos de entrada abaixo definem como
cada lancamento afeta a exposicao. O saldo disponivel deriva do somatorio
consolidado das entradas (Fase 2), nunca de colunas materializadas.
"""

from __future__ import annotations

from enum import StrEnum


class CreditEntryType(StrEnum):
    """Tipos de lancamento do ledger imutavel de credito."""

    LIMIT_SET = "LIMIT_SET"  # definicao/ajuste do limite pelo admin
    RESERVE = "RESERVE"  # reserva de exposicao em um pedido
    RELEASE = "RELEASE"  # liberacao de uma reserva
    INVOICE_CAPTURE = "INVOICE_CAPTURE"  # faturamento consome a exposicao
    PAYMENT = "PAYMENT"  # pagamento liquidado
    ADJUSTMENT = "ADJUSTMENT"  # ajuste manual auditado
