"""Regras do ledger de credito (compartilhadas, pure Python).

O saldo disponivel DERIVA do somatorio do ledger ``credit_entries``
(append-only). Compartilhado entre o contexto credit e ordering (que reserva
credito atomicamente ao criar um pedido faturado) sem acoplamento entre
bounded contexts. Cada tipo de entrada contribui com um sinal para a exposicao:

    LIMIT_SET        -> 0      (define o limite; nao e exposicao)
    RESERVE          -> +valor (reserva exposicao para um pedido)
    RELEASE          -> -valor (libera uma reserva)
    INVOICE_CAPTURE  -> +valor (reserva vira divida faturada)
    PAYMENT          -> -valor (pagamento liquidado)
    ADJUSTMENT       -> +valor (ajuste manual, ja vem sinalizado)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

_EXPOSURE_NEGATIVE_TYPES = frozenset({"RELEASE", "PAYMENT"})
_EXPOSURE_POSITIVE_TYPES = frozenset({"RESERVE", "INVOICE_CAPTURE", "ADJUSTMENT"})
_ZERO = Decimal("0")


@dataclass(frozen=True, kw_only=True)
class LedgerEntry:
    """Lancamento do ledger com tipo e valor (valor sempre positivo)."""

    entry_type: str
    amount: Decimal


def signed_amount(entry_type: str, amount: Decimal) -> Decimal:
    if entry_type in _EXPOSURE_NEGATIVE_TYPES:
        return -amount
    if entry_type in _EXPOSURE_POSITIVE_TYPES:
        return amount
    return _ZERO


def exposure(entries: Iterable[LedgerEntry]) -> Decimal:
    return sum((signed_amount(e.entry_type, e.amount) for e in entries), _ZERO)


def available_credit(credit_limit: Decimal, entries: Iterable[LedgerEntry]) -> Decimal:
    return credit_limit - exposure(entries)


def can_reserve(credit_limit: Decimal, entries: Iterable[LedgerEntry], amount: Decimal) -> bool:
    if amount <= 0:
        return False
    return available_credit(credit_limit, entries) >= amount
