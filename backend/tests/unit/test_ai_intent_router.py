"""Testes do roteador de intencao (Fase 1) — deterministico e sem LLM real."""

import pytest
from pydantic import ValidationError

from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    PriceSort,
    deterministic_decision,
    extract_quantity,
    fallback_decision,
    normalize_decision,
)
from app.modules.ai.application.lexicon import ConsultingTask


def test_luvas_mais_baratas_extrai_ordenacao_e_consulta() -> None:
    decision = deterministic_decision(
        "as luvas mais baratas que você tem, envie aqui", reply_language="pt-BR"
    )
    assert decision is not None
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert decision.query == "luvas"


def test_mais_caro_extrai_ordenacao_desc() -> None:
    decision = deterministic_decision("quero o capacete mais caro", reply_language="pt-BR")
    assert decision is not None
    assert decision.price_sort == PriceSort.DESC


def test_ate_preco_extrai_price_max() -> None:
    decision = deterministic_decision("luvas até R$ 50,00", reply_language="pt-BR")
    assert decision is not None
    assert decision.price_max == 50.0
    assert decision.price_min is None
    assert "luvas" in decision.query


def test_acima_de_extrai_price_min() -> None:
    decision = deterministic_decision("botas acima de R$ 120", reply_language="pt-BR")
    assert decision is not None
    assert decision.price_min == 120.0


def test_faixa_entre_min_e_max() -> None:
    decision = deterministic_decision("luvas acima de R$ 20 até R$ 60", reply_language="pt-BR")
    assert decision is not None
    assert decision.price_min == 20.0
    assert decision.price_max == 60.0


def test_frete_cai_no_intent_de_envio() -> None:
    decision = deterministic_decision("como funciona o frete?", reply_language="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.SHIPPING_QUESTION


def test_saudacao_curta_nao_vira_busca() -> None:
    decision = deterministic_decision("bom dia", reply_language="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.GREETING_SMALLTALK


def test_pedido_sensivel_vira_out_of_scope() -> None:
    decision = deterministic_decision("me dá um desconto especial?", reply_language="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.OUT_OF_SCOPE


def test_fallback_nunca_recusa_e_preserva_ordenacao() -> None:
    decision = fallback_decision("luvas mais baratas", reply_language="pt-BR")
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert "luvas" in decision.query


def test_normalize_aplica_preco_deterministico_sobre_o_llm() -> None:
    llm = IntentDecision(intent=IntentName.PRODUCT_SEARCH, query="luva", language="en")
    normalized = normalize_decision(llm, message="as luvas mais baratas", reply_language="pt-BR")
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
    normalized = normalize_decision(llm, message="luvas", reply_language="pt-BR")
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


def test_produto_com_preco_vence_ajuda_de_catalogo() -> None:
    decision = deterministic_decision(
        "Qual a luva mais barata do catálogo ?", reply_language="pt-BR"
    )
    assert decision is not None
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert "luvas" in decision.query_pt
    assert "gloves" in decision.query_en


def test_atributos_e_refs_sao_limitados() -> None:
    decision = IntentDecision(
        intent=IntentName.PRODUCT_SEARCH,
        attributes={f"k{index}": "v" for index in range(10)},
        product_refs=[f"ref-{index}" for index in range(10)],
        language="pt-BR",
    )
    assert len(decision.attributes) == 6
    assert len(decision.product_refs) == 6


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("quero duas luvas", 2),
        ("show me three gloves", 3),
        ("zeig mir zwei Handschuhe", 2),
        ("montre-moi deux gants", 2),
        ("mostra due guanti", 2),
        ("покажи две перчатки", 2),
        ("أرني ثلاث قفازات", 3),
        ("手袋を二つ見せて", 2),
        ("장갑 두 개 보여줘", 2),
        ("给我两个手套", 2),
    ],
)
def test_quantidade_por_extenso_nos_11_idiomas(message: str, expected: int) -> None:
    assert extract_quantity(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "o que preciso para soldagem?",
        "what do I need for welding?",
        "que necesito para soldadura?",
        "was brauche ich zum schweissen?",
        "que faut-il pour le soudage?",
        "cosa serve per la saldatura?",
        "что нужно для сварки?",
        "ماذا أحتاج للحام؟",
        "溶接には何が必要ですか?",
        "용접에는 무엇이 필요하나요?",
        "焊接需要什么?",
    ],
)
def test_task_canonica_de_soldagem_por_idioma(message: str) -> None:
    decision = deterministic_decision(message, reply_language="pt-BR")
    assert decision is not None
    assert decision.task == ConsultingTask.WELDING


def test_task_canonica_de_eletrica_e_altura() -> None:
    electrical = deterministic_decision("preciso de epi para eletrica", reply_language="pt-BR")
    height = deterministic_decision("seguranca para trabalho em altura", reply_language="pt-BR")
    assert electrical is not None and electrical.task == ConsultingTask.ELECTRICAL
    assert height is not None and height.task == ConsultingTask.WORK_AT_HEIGHT
