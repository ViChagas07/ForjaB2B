"""Adaptador de cambio de exibicao para o filtro de preco do chat.

Reutiliza o servico `GetFxRates` (BRL/base, cache Redis + Frankfurter). O chat
nunca inventa uma taxa: se o servico estiver indisponivel, devolve None e o
grafo pede confirmacao em BRL em vez de aplicar o valor estrangeiro.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.logging import get_logger
from app.domain.currency import SUPPORTED_CURRENCIES
from app.modules.fx.application.get_rates import GetFxRates

_logger = get_logger(__name__)


class FxCurrencyConverter:
    """`CurrencyConversionPort` sobre as taxas de exibicao do projeto."""

    def __init__(self, *, get_rates: GetFxRates) -> None:
        self._get_rates = get_rates

    @property
    def supported(self) -> frozenset[str]:
        return frozenset(SUPPORTED_CURRENCIES)

    async def to_brl(self, amount: float, *, currency: str) -> float | None:
        code = currency.strip().upper()
        if code == "BRL":
            return amount
        if code not in self.supported:
            return None
        try:
            view = await self._get_rates.run()
        except Exception as exc:  # noqa: BLE001 - cambio e opcional no chat
            _logger.warning("ai_currency_conversion_unavailable", currency=code, error=str(exc))
            return None
        rate = view.rates.rates.get(code)
        if rate is None or rate <= 0:
            _logger.warning("ai_currency_rate_missing", currency=code)
            return None
        return float(Decimal(str(amount)) / rate)
