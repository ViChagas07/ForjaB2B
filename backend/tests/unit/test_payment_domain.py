"""Testes unitarios do dominio de pagamento (maquina de estados e desconto PIX)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.payment.domain.enums import PaymentStatus
from app.modules.payment.domain.payment import can_transition, payable_amount, pix_discount_amount


def test_transicoes_validas_pending() -> None:
    assert can_transition(PaymentStatus.PENDING, PaymentStatus.PAID)
    assert can_transition(PaymentStatus.PENDING, PaymentStatus.FAILED)
    assert can_transition(PaymentStatus.PENDING, PaymentStatus.CANCELLED)


def test_transicao_paid_refunded() -> None:
    assert can_transition(PaymentStatus.PAID, PaymentStatus.REFUNDED)


def test_transicoes_invalidas_rejeitadas() -> None:
    assert not can_transition(PaymentStatus.PAID, PaymentStatus.PAID)
    assert not can_transition(PaymentStatus.PAID, PaymentStatus.FAILED)
    assert not can_transition(PaymentStatus.FAILED, PaymentStatus.PAID)
    assert not can_transition(PaymentStatus.REFUNDED, PaymentStatus.PAID)
    assert not can_transition(PaymentStatus.CANCELLED, PaymentStatus.PAID)


def test_desconto_pix_calculado_no_backend() -> None:
    assert pix_discount_amount(Decimal("100.00"), Decimal("0.05")) == Decimal("5.00")
    assert pix_discount_amount(Decimal("10.00"), Decimal("0.05")) == Decimal("0.50")


def test_desconto_pix_arredonda_meio_para_cima() -> None:
    assert pix_discount_amount(Decimal("99.99"), Decimal("0.05")) == Decimal("5.00")


def test_desconto_pix_zero_para_total_ou_taxa_nao_positivos() -> None:
    assert pix_discount_amount(Decimal("0.00"), Decimal("0.05")) == Decimal("0.00")
    assert pix_discount_amount(Decimal("100.00"), Decimal("0.00")) == Decimal("0.00")


def test_valor_a_pagar_subtrai_desconto() -> None:
    assert payable_amount(Decimal("10.00"), Decimal("0.50")) == Decimal("9.50")


def test_valor_a_pagar_nunca_negativo() -> None:
    assert payable_amount(Decimal("1.00"), Decimal("5.00")) == Decimal("0.00")
