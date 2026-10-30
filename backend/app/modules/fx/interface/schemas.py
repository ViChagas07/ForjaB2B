"""Contrato HTTP das taxas de cambio de exibicao."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.fx.domain.rates import SUPPORTED_CURRENCIES

CurrencyCode = Literal["BRL", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY"]


class FxRatesResponse(BaseModel):
    """Taxas com base BRL; a lista e sempre exatamente a fechada do dominio."""

    model_config = ConfigDict(extra="forbid")

    base: Literal["BRL"]
    rates: dict[CurrencyCode, Decimal]
    rate_date: date
    fetched_at: datetime
    source: str
    stale: bool

    @field_validator("rates")
    @classmethod
    def _validate_rates(cls, value: dict[CurrencyCode, Decimal]) -> dict[CurrencyCode, Decimal]:
        if set(value) != set(SUPPORTED_CURRENCIES):
            raise ValueError("rates must contain exactly the supported currencies")
        if value["BRL"] != Decimal("1"):
            raise ValueError("BRL rate must be 1")
        for code, rate in value.items():
            if not rate.is_finite() or rate <= 0:
                raise ValueError(f"rate for {code} must be positive and finite")
        return value
