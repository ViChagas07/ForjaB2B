"""Portas do contexto de cambio (dependencias invertidas).

O provedor externo e o cache Redis ficam atras destes contratos; o caso de uso
nao conhece HTTP, Redis nem o formato da Frankfurter.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.fx.domain.rates import FxRates


class FxRateProvider(Protocol):
    """Fonte externa de taxas com base BRL."""

    async def fetch_latest(self) -> FxRates:
        """Coleta as taxas mais recentes ou levanta `FxProviderError`."""


class FxRateCache(Protocol):
    """Cache das taxas (dado fresco e ultima conhecida) com lock de refresh."""

    async def load_fresh(self) -> FxRates | None:
        """Taxa dentro do TTL fresco; `None` em miss, expiracao ou cache fora."""

    async def load_last_known(self) -> FxRates | None:
        """Ultima taxa gravada, mesmo que ja tenha expirado o TTL fresco."""

    async def save(self, rates: FxRates) -> None:
        """Grava a taxa fresca e a copia de ultima conhecida."""

    async def acquire_refresh_lock(self) -> str | None:
        """Token do lock de refresh ou `None` quando outro processo o detem."""

    async def release_refresh_lock(self, token: str) -> None:
        """Libera o lock somente se o token ainda for o dono."""
