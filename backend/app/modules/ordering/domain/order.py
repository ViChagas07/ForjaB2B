"""Regras de dominio do pedido (pure Python, sem frameworks).

O pedido e um snapshot historico: os itens guardam sku/nome/preco/tier no momento
da compra e nao dependem do estado futuro do catalogo. Totais usam Decimal.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app.modules.ordering.domain.enums import OrderStatus

_ZERO = Decimal("0.00")

_CANCELLABLE = frozenset({OrderStatus.RECEIVED, OrderStatus.CREDIT_REVIEW})


def compute_subtotal(line_totals: Iterable[Decimal]) -> Decimal:
    """Subtotal = soma dos totais de linha (Decimal, sem ponto flutuante)."""
    return sum(line_totals, _ZERO)


def compute_total(
    *,
    subtotal: Decimal,
    discount_total: Decimal = _ZERO,
    shipping_total: Decimal = _ZERO,
    tax_total: Decimal = _ZERO,
) -> Decimal:
    """Total = subtotal + frete + impostos - descontos."""
    return subtotal + shipping_total + tax_total - discount_total


def can_cancel(status: OrderStatus) -> bool:
    """Cancelamento permitido apenas para pedidos ainda nao faturados."""
    return status in _CANCELLABLE
