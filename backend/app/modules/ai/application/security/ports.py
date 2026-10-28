"""Portas de apoio da seguranca de IA (implementacoes ficam na infrastructure)."""

from __future__ import annotations

import uuid
from typing import Protocol


class BlockCounter(Protocol):
    """Contador de bloqueios por conversa (anti-insistencia, item A.3)."""

    def register_block(self, conversation_id: uuid.UUID) -> int:
        """Registra um bloqueio e devolve o total acumulado da conversa."""
        ...


class InMemoryBlockCounter:
    """Contador em memoria (dev/testes); persistente (Redis) na FASE 3."""

    def __init__(self) -> None:
        self._counts: dict[uuid.UUID, int] = {}

    def register_block(self, conversation_id: uuid.UUID) -> int:
        count = self._counts.get(conversation_id, 0) + 1
        self._counts[conversation_id] = count
        return count

    def reset(self, conversation_id: uuid.UUID) -> None:
        self._counts.pop(conversation_id, None)
