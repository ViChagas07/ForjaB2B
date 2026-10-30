"""Moedas de EXIBICAO suportadas pelo produto.

Lista fechada compartilhada entre o contexto de cambio e o perfil da conta.
Nenhum valor financeiro e calculado aqui: os precos continuam em BRL.
"""

from __future__ import annotations

SUPPORTED_CURRENCIES: tuple[str, ...] = (
    "BRL",
    "USD",
    "EUR",
    "GBP",
    "CAD",
    "AUD",
    "JPY",
    "CNY",
)

BASE_CURRENCY = "BRL"
DEFAULT_CURRENCY = BASE_CURRENCY

QUOTE_CURRENCIES: tuple[str, ...] = tuple(
    code for code in SUPPORTED_CURRENCIES if code != BASE_CURRENCY
)


def normalize_currency(value: str | None) -> str:
    """Moeda da lista fechada (caixa alta) ou BRL para qualquer outro valor."""
    if value is None:
        return DEFAULT_CURRENCY
    candidate = value.strip().upper()
    if candidate in SUPPORTED_CURRENCIES:
        return candidate
    return DEFAULT_CURRENCY
