"""Regras de checkout compartilhadas por preview e criacao do pedido.

A oferta de recuperacao existente pode ser frete gratis ou 3% apenas nas linhas
sem preco negociado. O calculo fica aqui para que os dois fluxos usem a MESMA
regra e nao divirjam.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class RecoveryCalculation:
    """Efeito da oferta: desconto em produtos e/ou frete gratis."""

    discount: Decimal
    free_shipping: bool


def calculate_recovery(
    *, offer_type: str, percent: Decimal | None, eligible_product_total: Decimal
) -> RecoveryCalculation:
    """Calcula o beneficio da oferta sem I/O.

    ``PERCENT_DISCOUNT`` aplica o percentual somente sobre linhas nao
    negociadas; ``FREE_SHIPPING`` nao desconta produtos. Qualquer outro tipo
    (ou percentual ausente/invalido) nao produz beneficio.
    """
    if offer_type == "FREE_SHIPPING":
        return RecoveryCalculation(discount=_ZERO, free_shipping=True)
    if offer_type == "PERCENT_DISCOUNT" and percent is not None:
        if percent <= _ZERO or eligible_product_total <= _ZERO:
            return RecoveryCalculation(discount=_ZERO, free_shipping=False)
        raw = eligible_product_total * percent / _HUNDRED
        return RecoveryCalculation(
            discount=raw.quantize(_CENT, rounding=ROUND_HALF_UP),
            free_shipping=False,
        )
    return RecoveryCalculation(discount=_ZERO, free_shipping=False)
