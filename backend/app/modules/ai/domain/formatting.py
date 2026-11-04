"""Formatacao localizada de numeros e do valor BRL nas respostas do chat.

Nao ha dependencia externa: a tabela cobre os 11 locales da interface e os
separadores/rotulos usados nas respostas deterministicas. Os cartoes de
produto continuam devolvendo o valor decimal puro (a UI formata na moeda de
exibicao escolhida pelo usuario).
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.ai.domain.types import Locale

# locale -> (separador de milhar, separador decimal)
_NUMBER_FORMATS: dict[str, tuple[str, str]] = {
    "pt-BR": (".", ","),
    "en": (",", "."),
    "es": (".", ","),
    "de": (".", ","),
    "fr": (" ", ","),
    "it": (".", ","),
    "ru": (" ", ","),
    "ar": ("٬", "٫"),  # noqa: RUF001 - separadores arabes intencionais
    "ja": (",", "."),
    "ko": (",", "."),
    "zh-CN": (",", "."),
}

_CURRENCY_LABEL: dict[str, str] = {
    "pt-BR": "R$",
    "en": "BRL",
    "es": "R$",
    "de": "R$",
    "fr": "R$",
    "it": "R$",
    "ru": "R$",
    "ar": "R$",
    "ja": "R$",
    "ko": "R$",
    "zh-CN": "R$",
}


def format_number(value: float | Decimal, locale: Locale | str, *, decimals: int = 2) -> str:
    """Formata numero com agrupamento/decimal do locale (fallback pt-BR)."""
    key = locale.value if isinstance(locale, Locale) else str(locale)
    grouping, decimal = _NUMBER_FORMATS.get(key, _NUMBER_FORMATS["pt-BR"])
    rendered = f"{float(value):,.{max(0, decimals)}f}"
    if decimals <= 0:
        return rendered.replace(",", grouping)
    integer, fraction = rendered.rsplit(".", 1)
    return f"{integer.replace(',', grouping)}{decimal}{fraction}"


def format_brl(value: float | Decimal, locale: Locale | str, *, decimals: int = 2) -> str:
    """Valor do catalogo (BRL) com simbolo/rotulo e numero localizados."""
    key = locale.value if isinstance(locale, Locale) else str(locale)
    label = _CURRENCY_LABEL.get(key, "R$")
    return f"{label} {format_number(value, locale, decimals=decimals)}"


def format_foreign_amount(value: float, currency: str, locale: Locale | str) -> str:
    """Valor em moeda estrangeira para o pedido de confirmacao (sem converter)."""
    return f"{format_number(value, locale)} {currency}".strip()
