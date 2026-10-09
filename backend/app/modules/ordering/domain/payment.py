"""Vocabulario de pagamento do modulo ordering (pure Python)."""

from __future__ import annotations

from enum import StrEnum


class PaymentMethod(StrEnum):
    """Forma de pagamento de um pedido (simulada nesta fase)."""

    PIX = "PIX"  # pagamento a vista (nao consome credito)
    CARD = "CARD"  # cartao a vista (nao consome credito)
    BOLETO = "BOLETO"  # faturado (consome credito: reserva atomica)
