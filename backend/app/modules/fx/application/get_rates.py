"""Caso de uso: obter taxas BRL para exibicao, com cache e fallback.

Fluxo:
1. hit fresco -> devolve sem tocar no provedor;
2. miss -> disputa um lock curto no Redis (evita cache stampede);
3. quem obteve o lock revalida o cache (double check) e consulta o provedor;
4. falha do provedor -> devolve a ultima taxa conhecida marcada como stale;
5. sem taxa nenhuma -> `FxRatesUnavailableError` (503 com codigo estavel).

Quem nao obteve o lock espera brevemente pelo preenchimento feito pelo dono e,
se ainda assim nao houver dado, tambem recorre a ultima taxa conhecida.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.modules.fx.application.errors import FxProviderError, FxRatesUnavailableError
from app.modules.fx.application.ports import FxRateCache, FxRateProvider
from app.modules.fx.domain.rates import FxRates

_DEFAULT_REFRESH_WAIT_SECONDS = 2.0
_DEFAULT_POLL_INTERVAL_SECONDS = 0.05


@dataclass(frozen=True, kw_only=True)
class FxRatesView:
    """Taxas prontas para a interface, com a marca de dado desatualizado."""

    rates: FxRates
    stale: bool


class GetFxRates:
    """Orquestra cache, lock e provedor sem expor detalhes de infraestrutura."""

    def __init__(
        self,
        *,
        provider: FxRateProvider,
        cache: FxRateCache,
        refresh_wait_seconds: float = _DEFAULT_REFRESH_WAIT_SECONDS,
        poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._refresh_wait_seconds = refresh_wait_seconds
        self._poll_interval_seconds = poll_interval_seconds

    async def run(self) -> FxRatesView:
        fresh = await self._cache.load_fresh()
        if fresh is not None:
            return FxRatesView(rates=fresh, stale=False)

        token = await self._cache.acquire_refresh_lock()
        if token is None:
            return await self._wait_for_refresh_or_stale()

        try:
            fresh = await self._cache.load_fresh()
            if fresh is not None:
                return FxRatesView(rates=fresh, stale=False)

            try:
                latest = await self._provider.fetch_latest()
            except FxProviderError:
                stale = await self._cache.load_last_known()
                if stale is not None:
                    return FxRatesView(rates=stale, stale=True)
                raise FxRatesUnavailableError() from None

            await self._cache.save(latest)
            return FxRatesView(rates=latest, stale=False)
        finally:
            await self._cache.release_refresh_lock(token)

    async def _wait_for_refresh_or_stale(self) -> FxRatesView:
        deadline = time.monotonic() + self._refresh_wait_seconds
        while time.monotonic() < deadline:
            await asyncio.sleep(self._poll_interval_seconds)
            fresh = await self._cache.load_fresh()
            if fresh is not None:
                return FxRatesView(rates=fresh, stale=False)

        stale = await self._cache.load_last_known()
        if stale is not None:
            return FxRatesView(rates=stale, stale=True)
        raise FxRatesUnavailableError()
