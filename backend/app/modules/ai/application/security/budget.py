"""Orcamento diario de tokens e estimativa barata (item G.13).

`estimate_tokens` e uma aproximacao deterministica (chars/4) — suficiente
para contabilidade conservadora de orçamento, sem tokenizer externo.
`InMemoryDailyTokenBudget` reseta por dia UTC; a implementacao distribuida
(Redis) fica para a FASE 3 junto dos endpoints. Limite 0 = sem orcamento
(so o kill switch limita).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Protocol


def estimate_tokens(chars: int) -> int:
    """Aproximacao conservadora: 1 token ~ 4 caracteres (0 chars = 0 tokens)."""
    if chars <= 0:
        return 0
    return max(1, chars // 4)


class DailyTokenBudget(Protocol):
    """Contabilidade diaria de tokens estimados."""

    def try_consume(self, *, estimated_tokens: int) -> bool:
        """Consome do orcamento; False = orcamento estourado (429)."""
        ...


class InMemoryDailyTokenBudget:
    """Orcamento em memoria por processo, com reset diario UTC."""

    def __init__(self, *, limit: int, clock: Callable[[], date]) -> None:
        self._limit = limit
        self._clock = clock
        self._day: date | None = None
        self._used = 0

    def try_consume(self, *, estimated_tokens: int) -> bool:
        if self._limit <= 0:
            return True  # sem orcamento configurado
        self._maybe_reset()
        if self._used + estimated_tokens > self._limit:
            return False
        self._used += estimated_tokens
        return True

    @property
    def used(self) -> int:
        self._maybe_reset()
        return self._used

    def _maybe_reset(self) -> None:
        today = self._clock()
        if self._day != today:
            self._day = today
            self._used = 0
