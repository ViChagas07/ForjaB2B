"""Testes unitarios do dominio de credito (ledger append-only)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.credit.domain.ledger import (
    LedgerEntry,
    available_credit,
    can_reserve,
    exposure,
    signed_amount,
)

_LIMIT = Decimal("1000.00")


def _entry(entry_type: str, amount: str) -> LedgerEntry:
    return LedgerEntry(entry_type=entry_type, amount=Decimal(amount))


def test_signed_amount() -> None:
    assert signed_amount("RESERVE", Decimal("10")) == Decimal("10")
    assert signed_amount("INVOICE_CAPTURE", Decimal("10")) == Decimal("10")
    assert signed_amount("RELEASE", Decimal("10")) == Decimal("-10")
    assert signed_amount("PAYMENT", Decimal("10")) == Decimal("-10")
    assert signed_amount("LIMIT_SET", Decimal("1000")) == Decimal("0")


def test_disponivel_sem_movimentacao_igual_limite() -> None:
    assert available_credit(_LIMIT, []) == _LIMIT


def test_disponivel_apos_reserva() -> None:
    entries = [_entry("RESERVE", "250.00")]
    assert exposure(entries) == Decimal("250.00")
    assert available_credit(_LIMIT, entries) == Decimal("750.00")


def test_disponivel_apos_reserva_e_liberacao() -> None:
    entries = [_entry("RESERVE", "250.00"), _entry("RELEASE", "100.00")]
    assert exposure(entries) == Decimal("150.00")
    assert available_credit(_LIMIT, entries) == Decimal("850.00")


def test_pagamento_reduz_exposicao() -> None:
    entries = [_entry("INVOICE_CAPTURE", "400.00"), _entry("PAYMENT", "400.00")]
    assert exposure(entries) == Decimal("0.00")


def test_can_reserve_dentro_do_limite() -> None:
    entries = [_entry("RESERVE", "300.00")]
    assert can_reserve(_LIMIT, entries, Decimal("700.00")) is True


def test_can_reserve_exatamente_no_limite() -> None:
    entries = [_entry("RESERVE", "300.00")]
    assert can_reserve(_LIMIT, entries, Decimal("700.00")) is True
    assert can_reserve(_LIMIT, entries, Decimal("700.01")) is False


def test_can_reserve_acima_do_limite() -> None:
    entries = [_entry("RESERVE", "900.00")]
    assert can_reserve(_LIMIT, entries, Decimal("100.01")) is False


def test_can_reserve_valor_negativo_ou_zero() -> None:
    assert can_reserve(_LIMIT, [], Decimal("0")) is False
    assert can_reserve(_LIMIT, [], Decimal("-1")) is False


def test_valores_sem_erro_de_ponto_flutuante() -> None:
    entries = [_entry("RESERVE", "0.10"), _entry("RESERVE", "0.20")]
    assert exposure(entries) == Decimal("0.30")
    assert available_credit(_LIMIT, entries) == Decimal("999.70")
