"""Vocabulario de estado do modulo ordering (pure Python, sem frameworks).

A maquina de estados (transicoes validas) e responsabilidade da Fase 2
(dominio/backend). Aqui ficam apenas os estados aceitos pela persistencia.
"""

from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    """Estados do pedido, conforme o MEGA-PROMPT (secao 5)."""

    RECEIVED = "RECEIVED"
    CREDIT_REVIEW = "CREDIT_REVIEW"
    INVOICED = "INVOICED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    CREDIT_REJECTED = "CREDIT_REJECTED"
