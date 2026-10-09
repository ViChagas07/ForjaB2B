"""Vocabulario de estado do modulo payment (pure Python, sem frameworks)."""

from __future__ import annotations

from enum import StrEnum


class PaymentStatus(StrEnum):
    """Situacao de um pagamento (maquina de estados no dominio)."""

    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentMethod(StrEnum):
    """Forma de pagamento suportada pelo fluxo de checkout/pagamento."""

    PIX = "PIX"  # a vista, com desconto simulado
    CARD = "CARD"  # cartao (adaptador Fake/local; Stripe em teste no futuro)
    BOLETO = "BOLETO"  # quita uma fatura ja emitida (credito faturado)


class PaymentEventOutcome(StrEnum):
    """Resultado do processamento de um evento de webhook."""

    APPLIED = "APPLIED"  # transicao aplicada
    DUPLICATE = "DUPLICATE"  # evento ja processado (idempotencia)
    REJECTED = "REJECTED"  # transicao invalida (evento fora de ordem/invalido)
