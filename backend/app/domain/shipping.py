"""Regras de frete do Forja (simulacao deterministica, sem transportadora).

O frete e calculado no backend a partir do peso real do catalogo
(``products.weight_kg`` x quantidade). Nunca confiar no peso enviado pelo
cliente. Implementacao fake/deterministica para portfolio: sem API externa e
reproduzivel em testes.

Peso e dinheiro sempre em ``Decimal``; nenhum ponto flutuante.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")

# Tarifa fake/deterministica (portfolio). Mantida como constantes reproduziveis;
# se um dia houver configuracao regional, vira configuracao/env (sem mudar a
# assinatura pura do calculo).
BASE_FREIGHT = Decimal("15.00")
RATE_PER_KG = Decimal("5.00")


def compute_total_weight(line_weights: Iterable[tuple[int, Decimal | None]]) -> Decimal:
    """Peso total = soma(quantidade x peso_kg); peso ausente (None) conta como 0.

    Recebe ``(quantity, weight_kg)`` por linha para nunca confiar em um peso
    agregado vindo do cliente.
    """
    total = _ZERO
    for quantity, weight_kg in line_weights:
        if weight_kg is not None:
            total += quantity * weight_kg
    return total


def compute_shipping(*, total_weight_kg: Decimal) -> Decimal:
    """Frete = base + (por kg * peso); peso zero/ausente -> frete zero.

    Deterministico: mesmos pesos produzem sempre o mesmo valor, com
    arredondamento monetario ROUND_HALF_UP.
    """
    if total_weight_kg <= 0:
        return _ZERO
    return (BASE_FREIGHT + RATE_PER_KG * total_weight_kg).quantize(_CENT, ROUND_HALF_UP)
