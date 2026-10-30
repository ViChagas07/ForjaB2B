"""Adaptador da Frankfurter (taxas de referencia do Banco Central Europeu).

Endpoint fixo no servidor: a URL nao recebe nenhuma entrada do usuario. As
moedas consultadas sao a lista fechada do dominio, serializada como constante.
Nao ha chave, cadastro nem biblioteca especifica: usa o httpx ja presente.

O endpoint v2 por provedor foi escolhido em vez do v1 (deprecado) e do v2
blendado para que a fonte exibida corresponda exatamente ao provedor usado:
`/v2/providers/ecb/rates`. A resposta e uma lista de linhas
`{date, base, quote, rate}` e o campo `date` e a data de referencia da taxa
(publicacao do BCE), nao a data em que o servidor consultou.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.modules.fx.application.errors import FxProviderError
from app.modules.fx.domain.rates import BASE_CURRENCY, QUOTE_CURRENCIES, FxRates

_BASE_URL = "https://api.frankfurter.dev"
_RATES_PATH = "/v2/providers/ecb/rates"
_QUOTES_PARAM = ",".join(QUOTE_CURRENCIES)
_SOURCE = "Frankfurter / European Central Bank"
_DEFAULT_TIMEOUT_SECONDS = 5.0
_DEFAULT_MAX_RETRIES = 1


def _utc_now() -> datetime:
    return datetime.now(UTC)


class FrankfurterFxRateProvider:
    """Coleta as taxas com timeout curto e no maximo um retry."""

    def __init__(
        self,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=timeout_seconds,
            transport=transport,
        )
        self._max_retries = max(0, max_retries)
        self._clock = clock

    async def fetch_latest(self) -> FxRates:
        last_error = FxProviderError("fx provider unavailable")
        for attempt in range(self._max_retries + 1):
            try:
                return await self._fetch_once()
            except FxProviderError as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
        raise last_error

    async def _fetch_once(self) -> FxRates:
        try:
            response = await self._client.get(
                _RATES_PATH,
                params={"base": BASE_CURRENCY, "quotes": _QUOTES_PARAM},
            )
        except httpx.TimeoutException as exc:
            raise FxProviderError("fx provider timeout") from exc
        except httpx.HTTPError as exc:
            raise FxProviderError("fx provider request failed") from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise FxProviderError("fx provider unavailable")
        if response.status_code >= 400:
            raise FxProviderError("fx provider rejected request")

        try:
            payload: object = response.json()
            return self._parse(payload)
        except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
            raise FxProviderError("fx provider invalid payload") from exc

    def _parse(self, payload: object) -> FxRates:
        if not isinstance(payload, list) or not payload:
            raise ValueError("fx payload must be a non-empty list")

        collected: dict[str, Decimal] = {}
        reference_dates: set[date] = set()

        for row in payload:
            parsed = self._parse_row(row)
            if parsed is None:
                continue
            quote, reference_date, rate = parsed
            if quote in collected:
                raise ValueError("fx payload has duplicate quotes")
            collected[quote] = rate
            reference_dates.add(reference_date)

        if set(collected) != set(QUOTE_CURRENCIES):
            raise ValueError("fx payload is missing supported currencies")
        if len(reference_dates) != 1:
            raise ValueError("fx payload has mixed reference dates")

        rates: dict[str, Decimal] = {BASE_CURRENCY: Decimal("1")}
        rates.update(collected)
        return FxRates(
            rates=rates,
            rate_date=reference_dates.pop(),
            fetched_at=self._clock(),
            source=_SOURCE,
        )

    def _parse_row(self, row: object) -> tuple[str, date, Decimal] | None:
        if not isinstance(row, dict):
            raise ValueError("fx row must be an object")
        raw_quote = row.get("quote")
        if not isinstance(raw_quote, str):
            raise ValueError("fx row quote must be a string")
        quote = raw_quote.strip().upper()
        if quote not in QUOTE_CURRENCIES:
            return None
        if row.get("base") != BASE_CURRENCY:
            raise ValueError("fx row base must be BRL")

        raw_rate = row.get("rate")
        if isinstance(raw_rate, bool) or not isinstance(raw_rate, (int, float, str)):
            raise ValueError("fx row rate must be numeric")
        rate = Decimal(str(raw_rate))
        if not rate.is_finite() or rate <= 0:
            raise ValueError("fx row rate must be positive and finite")

        raw_date = row.get("date")
        if not isinstance(raw_date, str):
            raise ValueError("fx row date must be a string")
        return quote, date.fromisoformat(raw_date), rate

    async def aclose(self) -> None:
        await self._client.aclose()
