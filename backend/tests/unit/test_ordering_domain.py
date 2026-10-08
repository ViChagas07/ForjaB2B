"""Testes unitarios do dominio de pedidos (totais e transicoes de estado)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.ordering.domain.enums import OrderStatus
from app.modules.ordering.domain.order import can_cancel, compute_subtotal, compute_total


def test_compute_subtotal() -> None:
    assert compute_subtotal([Decimal("10.00"), Decimal("20.50")]) == Decimal("30.50")


def test_compute_subtotal_vazio() -> None:
    assert compute_subtotal([]) == Decimal("0.00")


def test_compute_total_sem_taxas() -> None:
    assert compute_total(subtotal=Decimal("30.50")) == Decimal("30.50")


def test_compute_total_com_frete_e_imposto() -> None:
    assert compute_total(
        subtotal=Decimal("100.00"), shipping_total=Decimal("10.00"), tax_total=Decimal("5.00")
    ) == Decimal("115.00")


def test_compute_total_com_desconto() -> None:
    assert compute_total(subtotal=Decimal("100.00"), discount_total=Decimal("20.00")) == Decimal(
        "80.00"
    )


def test_cancelamento_permitido_para_recebido() -> None:
    assert can_cancel(OrderStatus.RECEIVED) is True
    assert can_cancel(OrderStatus.CREDIT_REVIEW) is True


def test_cancelamento_negado_para_faturado() -> None:
    assert can_cancel(OrderStatus.INVOICED) is False
    assert can_cancel(OrderStatus.DELIVERED) is False
    assert can_cancel(OrderStatus.CANCELLED) is False
