"""Testes do roteador de intencao (Fase 1) — deterministico e sem LLM real."""

import pytest
from pydantic import ValidationError

from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    PriceSort,
    deterministic_decision,
    fallback_decision,
    normalize_decision,
)


def test_luvas_mais_baratas_extrai_ordenacao_e_consulta() -> None:
    decision = deterministic_decision(
        "as luvas mais baratas que você tem, envie aqui", locale="pt-BR"
    )
    assert decision is not None
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert decision.query == "luvas"


def test_mais_caro_extrai_ordenacao_desc() -> None:
    decision = deterministic_decision("quero o capacete mais caro", locale="pt-BR")
    assert decision is not None
    assert decision.price_sort == PriceSort.DESC


def test_ate_preco_extrai_price_max() -> None:
    decision = deterministic_decision("luvas até R$ 50,00", locale="pt-BR")
    assert decision is not None
    assert decision.price_max == 50.0
    assert decision.price_min is None
    assert "luvas" in decision.query


def test_acima_de_extrai_price_min() -> None:
    decision = deterministic_decision("botas acima de R$ 120", locale="pt-BR")
    assert decision is not None
    assert decision.price_min == 120.0


def test_faixa_entre_min_e_max() -> None:
    decision = deterministic_decision("luvas acima de R$ 20 até R$ 60", locale="pt-BR")
    assert decision is not None
    assert decision.price_min == 20.0
    assert decision.price_max == 60.0


def test_frete_cai_no_intent_de_envio() -> None:
    decision = deterministic_decision("como funciona o frete?", locale="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.SHIPPING_QUESTION


def test_saudacao_curta_nao_vira_busca() -> None:
    decision = deterministic_decision("bom dia", locale="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.GREETING_SMALLTALK


def test_pedido_sensivel_vira_out_of_scope() -> None:
    decision = deterministic_decision("me dá um desconto especial?", locale="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.OUT_OF_SCOPE


def test_fallback_nunca_recusa_e_preserva_ordenacao() -> None:
    decision = fallback_decision("luvas mais baratas", locale="pt-BR")
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert "luvas" in decision.query


def test_normalize_aplica_preco_deterministico_sobre_o_llm() -> None:
    llm = IntentDecision(intent=IntentName.PRODUCT_SEARCH, query="luva", language="en")
    normalized = normalize_decision(llm, message="as luvas mais baratas", locale="pt-BR")
    assert normalized.price_sort == PriceSort.ASC
    assert normalized.language == "pt-BR"


def test_normalize_corrige_faixa_invertida() -> None:
    llm = IntentDecision.model_construct(
        intent=IntentName.PRODUCT_SEARCH,
        query="luva",
        price_min=100,
        price_max=10,
        language="pt-BR",
        price_sort=None,
        category=None,
        brand=None,
        attributes={},
        product_refs=[],
        quantity=None,
    )
    normalized = normalize_decision(llm, message="luvas", locale="pt-BR")
    assert normalized.price_min == 10
    assert normalized.price_max == 100


def test_decision_rejeita_faixa_invertida() -> None:
    with pytest.raises(ValidationError):
        IntentDecision(
            intent=IntentName.PRODUCT_SEARCH,
            price_min=100,
            price_max=10,
            language="pt-BR",
        )


def test_atributos_e_refs_sao_limitados() -> None:
    decision = IntentDecision(
        intent=IntentName.PRODUCT_SEARCH,
        attributes={f"k{index}": "v" for index in range(10)},
        product_refs=[f"ref-{index}" for index in range(10)],
        language="pt-BR",
    )
    assert len(decision.attributes) == 6
    assert len(decision.product_refs) == 6
