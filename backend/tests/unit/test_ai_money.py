# ruff: noqa: RUF001 - digitos/separadores arabes intencionais
"""Dinheiro/moeda/filtros do roteador: separadores locais, faixas e moedas."""

from __future__ import annotations

import pytest

from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    PriceSort,
    deterministic_decision,
    normalize_decision,
)
from app.modules.ai.application.money import (
    detect_currency,
    extract_money_amounts,
    extract_price_filters,
    parse_amount,
    strip_money_from_query,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1 234,56", 1234.56),
        ("1234.56", 1234.56),
        ("1.234", 1234.0),
        ("50", 50.0),
        ("١٬٢٣٤٫٥٦", 1234.56),
    ],
)
def test_parse_amount_locais(raw: str, expected: float) -> None:
    assert parse_amount(raw) == pytest.approx(expected)


def test_detecta_moeda_por_simbolo_codigo_e_nome() -> None:
    assert detect_currency("R$ 50") == "BRL"
    assert detect_currency("50 EUR") == "EUR"
    assert detect_currency("US$ 50") == "USD"
    assert detect_currency("50 dolares") == "USD"
    assert detect_currency("50 reais") == "BRL"
    assert detect_currency("¥ 50") == "JPY"
    assert detect_currency("50 RMB") == "CNY"
    assert detect_currency("50") is None


def test_extrai_valor_com_moeda_e_digitos_arabes() -> None:
    amounts = extract_money_amounts("50 EUR e ١٠٠ دولار")
    assert amounts[0].value == 50
    assert amounts[0].currency == "EUR"
    assert amounts[1].value == 100
    assert amounts[1].currency == "USD"


def test_faixa_entre_dois_valores() -> None:
    filters = extract_price_filters("luvas entre 50 e 100 EUR")
    assert filters.min == 50
    assert filters.max == 100
    assert filters.currency == "EUR"
    assert filters.needs_confirmation is False


def test_faixa_entre_valores_em_brl() -> None:
    filters = extract_price_filters("luvas entre R$ 1.234,56 e R$ 2.000,00")
    assert filters.min == pytest.approx(1234.56)
    assert filters.max == pytest.approx(2000.0)
    assert filters.currency == "BRL"


def test_moeda_suportada_nao_e_confirmada() -> None:
    filters = extract_price_filters("luvas até 50 EUR")
    assert filters.max == 50
    assert filters.currency == "EUR"
    assert filters.needs_confirmation is False


def test_moeda_nao_suportada_exige_confirmacao() -> None:
    filters = extract_price_filters("luvas até 50 CHF")
    assert filters.max == 50
    assert filters.currency == "CHF"
    assert filters.needs_confirmation is True


def test_moedas_misturadas_exigem_confirmacao() -> None:
    filters = extract_price_filters("luvas até 50 EUR e 100 USD")
    assert filters.needs_confirmation is True


def test_sem_simbolo_assume_brl() -> None:
    filters = extract_price_filters("luvas até 50")
    assert filters.max == 50
    assert filters.currency == "BRL"
    assert filters.needs_confirmation is False


def test_ordenacao_e_range_nao_viram_consulta() -> None:
    filters = extract_price_filters("luvas mais baratas até R$ 50")
    assert filters.sort == "asc"
    assert filters.max == 50
    assert strip_money_from_query("luvas até R$ 50") == "luvas"


def test_normalize_nao_trata_50_eur_como_brl() -> None:
    decision = IntentDecision(
        intent=IntentName.PRODUCT_SEARCH,
        query="luvas",
        price_max=50,
        language="pt-BR",
    )
    normalized = normalize_decision(decision, message="luvas até 50 EUR", reply_language="pt-BR")
    assert normalized.price_max == 50
    assert normalized.price_currency == "EUR"
    assert normalized.price_currency_confirmation is False


def test_normalize_marca_confirmacao_para_moeda_desconhecida() -> None:
    decision = IntentDecision(
        intent=IntentName.PRODUCT_SEARCH,
        query="luvas",
        price_max=50,
        language="pt-BR",
    )
    normalized = normalize_decision(decision, message="luvas até 50 CHF", reply_language="pt-BR")
    assert normalized.price_currency == "CHF"
    assert normalized.price_currency_confirmation is True


def test_deterministico_reconhece_faixa_e_ordenacao() -> None:
    decision = deterministic_decision(
        "handschuhe zwischen 10 und 50 EUR, günstigste zuerst", reply_language="de"
    )
    assert decision is not None
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert decision.price_min == 10
    assert decision.price_max == 50
    assert decision.price_currency == "EUR"


@pytest.mark.parametrize(
    ("message", "minimum", "maximum", "currency"),
    [
        ("luvas até cinquenta reais", None, 50, "BRL"),
        ("gloves under fifty dollars", None, 50, "USD"),
        ("luvas entre cinquenta e cem reais", 50, 100, "BRL"),
        ("luvas até vinte e cinco reais", None, 25, "BRL"),
        ("guantes hasta cien euros", None, 100, "EUR"),
        ("handschuhe bis hundert euro", None, 100, "EUR"),
        ("gants jusqu'à cent euros", None, 100, "EUR"),
        ("guanti fino a cento euro", None, 100, "EUR"),
        ("перчатки до ста рублей", None, 100, "RUB"),
        ("قفازات حتى مئة دولار", None, 100, "USD"),
        ("手袋 百元以下", None, 100, "CNY"),
        ("장갑 백 원 이하", None, 100, "KRW"),
    ],
)
def test_numeros_por_extenso_em_precos(
    message: str, minimum: float | None, maximum: float | None, currency: str
) -> None:
    filters = extract_price_filters(message)
    assert filters.min == minimum
    assert filters.max == maximum
    assert filters.currency == currency
