"""Regras de dominio do pagamento (pure Python, sem frameworks).

A maquina de estados e explicita: apenas as transicoes abaixo sao validas.
Dinheiro sempre em ``Decimal`` com arredondamento ``ROUND_HALF_UP``. O desconto
PIX e calculado no backend (nunca a partir de valor enviado pelo cliente).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.modules.payment.domain.enums import PaymentStatus

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")

# Transicoes validas da maquina de estados de pagamento.
_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING: frozenset(
        {PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.CANCELLED}
    ),
    PaymentStatus.PAID: frozenset({PaymentStatus.REFUNDED}),
}


def can_transition(current: PaymentStatus, target: PaymentStatus) -> bool:
    """Indica se a transicao ``current -> target`` e valida."""
    return target in _TRANSITIONS.get(current, frozenset())


def pix_discount_amount(total: Decimal, rate: Decimal) -> Decimal:
    """Desconto PIX = total * rate (arredondado). Total/rate nao positivos -> zero."""
    if total <= _ZERO or rate <= _ZERO:
        return _ZERO
    return (total * rate).quantize(_CENT, rounding=ROUND_HALF_UP)


def payable_amount(total: Decimal, discount: Decimal) -> Decimal:
    """Valor a pagar = total - desconto, nunca negativo."""
    amount = total - discount
    return amount if amount > _ZERO else _ZERO
