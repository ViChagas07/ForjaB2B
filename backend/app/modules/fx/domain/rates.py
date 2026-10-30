"""Tipos e regras do cambio de EXIBICAO.

A lista de moedas e FECHADA e a base e sempre BRL. Uma taxa representa quantas
unidades da moeda de destino equivalem a 1 BRL; BRL vale exatamente 1. O
dominio nao calcula dinheiro: apenas guarda multiplicadores exatos (Decimal)
para que o frontend aproxime a exibicao.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType

from app.domain.currency import (
    BASE_CURRENCY,
    DEFAULT_CURRENCY,
    QUOTE_CURRENCIES,
    SUPPORTED_CURRENCIES,
    normalize_currency,
)

__all__ = [
    "BASE_CURRENCY",
    "DEFAULT_CURRENCY",
    "QUOTE_CURRENCIES",
    "SUPPORTED_CURRENCIES",
    "FxRates",
    "normalize_currency",
]


@dataclass(frozen=True, kw_only=True)
class FxRates:
    """Taxas de referencia com a data do provedor e o instante da coleta."""

    rates: Mapping[str, Decimal]
    rate_date: date
    fetched_at: datetime
    source: str
    base: str = BASE_CURRENCY

    def __post_init__(self) -> None:
        if self.base != BASE_CURRENCY:
            raise ValueError("fx base must be BRL")
        if set(self.rates) != set(SUPPORTED_CURRENCIES):
            raise ValueError("fx rates must contain exactly the supported currencies")
        if self.rates[BASE_CURRENCY] != Decimal("1"):
            raise ValueError("fx BRL rate must be 1")
        for code, rate in self.rates.items():
            if not isinstance(rate, Decimal):
                raise TypeError(f"fx rate for {code} must be Decimal")
            if not rate.is_finite() or rate <= 0:
                raise ValueError(f"fx rate for {code} must be a positive finite value")
        if not self.source.strip():
            raise ValueError("fx source must not be empty")
        object.__setattr__(self, "rates", MappingProxyType(dict(self.rates)))

    def rate_for(self, currency: str) -> Decimal:
        """Taxa de 1 BRL para a moeda (BRL = 1); moeda fora da lista cai em BRL."""
        return self.rates[normalize_currency(currency)]
