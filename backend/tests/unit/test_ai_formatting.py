"""Formatacao localizada de numeros/moeda nas respostas deterministicas."""

from __future__ import annotations

from app.modules.ai.domain.formatting import format_brl, format_number
from app.modules.ai.domain.types import Locale


def test_formata_numero_por_locale() -> None:
    assert format_number(1234.56, Locale.PT_BR) == "1.234,56"
    assert format_number(1234.56, Locale.EN) == "1,234.56"
    assert format_number(1234.56, Locale.DE) == "1.234,56"
    assert format_number(1234.56, Locale.FR) == "1 234,56"
    assert format_number(1234.56, Locale.RU) == "1 234,56"
    assert format_number(1234.56, Locale.AR) == "1٬234٫56"  # noqa: RUF001
    assert format_number(1234.56, Locale.JA) == "1,234.56"
    assert format_number(1234.56, Locale.KO) == "1,234.56"
    assert format_number(1234.56, Locale.ZH_CN) == "1,234.56"


def test_formata_brl_com_rotulo_localizado() -> None:
    assert format_brl(15, Locale.PT_BR) == "R$ 15,00"
    assert format_brl(15, Locale.EN) == "BRL 15.00"
    assert format_brl(15, Locale.FR) == "R$ 15,00"
    assert format_brl(15, Locale.AR) == "R$ 15٫00"  # noqa: RUF001
