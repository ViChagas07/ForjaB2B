# ruff: noqa: RUF001 - mensagens intencionais em cirilico/arabe/japones/coreano/chines
"""Regressao do assistente confiavel: idioma, existencia, moeda e fallback."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.modules.ai.application.chat import ChatService
from app.modules.ai.application.conversation_service import ConversationScope
from app.modules.ai.application.errors import LLMUnavailableError
from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    deterministic_decision,
    normalize_decision,
)
from app.modules.ai.application.query_normalization import normalize_query
from app.modules.ai.domain.degradation import (
    catalog_mode_response,
    catalog_results_response,
    existence_found_response,
    existence_not_found_response,
)
from app.modules.ai.domain.language import (
    LanguageDetection,
    guard_language_diverges,
    resolve_reply_language,
)
from app.modules.ai.domain.types import Locale
from app.modules.ai.infrastructure.llm_health import LLMHealthProbe
from app.modules.ai.infrastructure.llm_openai import LangChainOpenAILLM
from tests.unit.test_ai_chat_graph import (
    CONVERSATION,
    FakeSearch,
    auth_like,
    build,
    product,
)


class _DetectorES:
    def detect(self, text: str) -> LanguageDetection:
        return LanguageDetection(language=Locale.ES, confidence=0.99, source="detector")


def test_idioma_pt_curto_vence_langid_espanhol() -> None:
    result = resolve_reply_language(
        message="A loja tem prensa hidráulica?",
        detection=_DetectorES().detect(""),
        conversation_language="pt-BR",
        site_locale="pt-BR",
    )
    assert result.language is Locale.PT_BR


@pytest.mark.parametrize(
    ("message", "expected_product"),
    [
        ("A loja tem prensa hidráulica?", "prensa hidráulica"),
        ("A loja tem abafador de ruído?", "abafador de ruído"),
        ("vocês vendem capacete?", "capacete"),
        ("tem luva nitrílica em estoque?", "luva nitrílica"),
        ("do you have gloves?", "gloves"),
        ("¿tienen casco?", "casco"),
        ("haben Sie Schutzbrillen?", "Schutzbrillen"),
        ("avez-vous des gants ?", "gants"),
        ("avete guanti?", "guanti"),
        ("у вас есть перчатки?", "перчатки"),
        ("هل لديكم خوذة؟", "خوذة"),
        ("ヘルメットはありますか", "ヘルメット"),
        ("장갑 있나요", "장갑"),
        ("你们有手套吗", "手套"),
    ],
)
def test_existencia_por_codigo_nos_11_idiomas(message: str, expected_product: str) -> None:
    decision = deterministic_decision(message, reply_language="pt-BR")
    assert decision is not None
    assert decision.availability_check is True
    assert decision.intent is IntentName.AVAILABILITY
    assert expected_product.casefold() in decision.query.casefold()


def test_moeda_fantasma_sem_preco_e_descartada() -> None:
    decision = IntentDecision(
        intent=IntentName.PRODUCT_SEARCH,
        query="prensa hidraulica",
        price_currency="BRL",
        price_currency_confirmation=True,
    )
    normalized = normalize_decision(
        decision, message="A loja tem prensa hidráulica?", reply_language="pt-BR"
    )
    assert normalized.availability_check is True
    assert normalized.price_currency_confirmation is False


def test_range_inventado_sem_contexto_de_preco_e_descartado() -> None:
    decision = IntentDecision(
        intent=IntentName.PRODUCT_SEARCH,
        query="luva",
        price_min=10,
        price_max=50,
        price_currency_confirmation=True,
    )
    normalized = normalize_decision(decision, message="quero uma luva", reply_language="pt-BR")
    assert normalized.price_min is None
    assert normalized.price_max is None
    assert normalized.price_currency_confirmation is False


def test_sinonimos_de_dominio() -> None:
    assert normalize_query("abafador de ruído")[0] == "protetor auricular"
    assert normalize_query("lente de segurança")[0].startswith("oculos")
    assert normalize_query("casco")[0] == "capacete"
    assert normalize_query("prensa hidráulica")[0] == "prensa hidraulica"


async def test_existencia_achou_responde_template_e_cartoes_sem_llm() -> None:
    graph, conversations, _audit, history = build(llm=None, products=[product()])
    result = await graph.run(
        conversation=CONVERSATION,
        reply_language="pt-BR",
        message="A loja tem capacete?",
        history=history,
        auth=auth_like(),
    )
    assert result.reply == existence_found_response(Locale.PT_BR)
    assert [card.product_id for card in result.cards]
    assert result.degraded is False
    assert conversations.assistants == [existence_found_response(Locale.PT_BR)]


async def test_existencia_nao_achou_sugere_categoria_real() -> None:
    graph, _conversations, _audit, history = build(
        llm=None, search_port=FakeSearch([]), products=[]
    )
    result = await graph.run(
        conversation=CONVERSATION,
        reply_language="pt-BR",
        message="A loja tem torno mecânico?",
        history=history,
        auth=auth_like(),
    )
    assert result.reply == existence_not_found_response(
        Locale.PT_BR, categories=("EPI (3)",)
    )
    assert result.cards == []
    assert result.degraded is False


async def test_auditoria_falhando_nao_derruba_resposta() -> None:
    graph, _conversations, _audit, history = build(llm=None, products=[product()])

    class _FailingAudit:
        async def record(self, **kwargs: object) -> None:
            raise RuntimeError("constraint legada")

    graph._audit = _FailingAudit()
    result = await graph.run(
        conversation=CONVERSATION,
        reply_language="pt-BR",
        message="A loja tem capacete?",
        history=history,
        auth=auth_like(),
    )
    assert result.reply == existence_found_response(Locale.PT_BR)


def test_guard_aceita_resposta_pt_curta_com_termo_forte() -> None:
    assert (
        guard_language_diverges(
            "Sim, encontrei estas opções.",
            expected=Locale.PT_BR,
            detector=_DetectorES(),
        )
        is False
    )


async def test_llm_com_reasoning_sem_content_repete_com_thinking_off() -> None:
    adapter = LangChainOpenAILLM(
        base_url="http://localhost:9/v1",
        api_key="x",
        model="m",
        timeout_seconds=1.0,
        max_tokens=32,
    )
    calls: list[tuple[int, bool]] = []
    responses = [
        AIMessage(
            content="",
            additional_kwargs={"reasoning_content": "pensando..."},
            response_metadata={"finish_reason": "length"},
        ),
        AIMessage(content="ok", response_metadata={"finish_reason": "stop"}),
    ]

    async def fake_invoke(messages, temperature, max_tokens, *, disable_thinking):
        calls.append((max_tokens, disable_thinking))
        return responses.pop(0)

    adapter._invoke_raw = fake_invoke  # type: ignore[method-assign]
    text = await adapter.complete_text(messages=[{"role": "user", "content": "oi"}])
    assert text == "ok"
    assert calls[0] == (32, False)
    assert calls[1][0] > calls[0][0]
    assert calls[1][1] is True


async def test_llm_vazio_apos_retry_falha_com_kind_recuperavel() -> None:
    adapter = LangChainOpenAILLM(
        base_url="http://localhost:9/v1",
        api_key="x",
        model="m",
        timeout_seconds=1.0,
        max_tokens=32,
    )

    async def fake_invoke(messages, temperature, max_tokens, *, disable_thinking):
        return AIMessage(
            content="",
            additional_kwargs={"reasoning_content": "só raciocínio"},
            response_metadata={"finish_reason": "length"},
        )

    adapter._invoke_raw = fake_invoke  # type: ignore[method-assign]
    with pytest.raises(LLMUnavailableError) as excinfo:
        await adapter.complete_text(messages=[{"role": "user", "content": "oi"}])
    assert excinfo.value.kind in {"reasoning_only", "truncated"}


async def test_structured_recupera_reasoning_com_retry() -> None:
    from pydantic import BaseModel

    class _Card(BaseModel):
        sku: str

    adapter = LangChainOpenAILLM(
        base_url="http://localhost:9/v1",
        api_key="x",
        model="m",
        timeout_seconds=1.0,
        max_tokens=32,
    )
    calls: list[tuple[int, bool]] = []

    async def fake_once(schema, messages, temperature, max_tokens, *, disable_thinking):
        calls.append((max_tokens, disable_thinking))
        if len(calls) == 1:
            raise LLMUnavailableError("reasoning", kind="reasoning_only")
        return _Card(sku="CAP-001")

    adapter._structured_once = fake_once  # type: ignore[method-assign]
    result = await adapter.complete_structured(
        schema=_Card, messages=[{"role": "user", "content": "oi"}]
    )
    assert result.sku == "CAP-001"
    assert calls[1][1] is True
    assert calls[1][0] > calls[0][0]


async def test_health_llm_exige_geracao_real() -> None:
    probe = LLMHealthProbe(
        enabled=True,
        base_url="http://localhost:9/v1",
        model="m",
        fetch_model_ids=lambda: _ids({"m"}),
        fetch_generation=lambda: _bool(False),
    )
    result = await probe.check()
    assert result.available is False


async def test_chat_service_cai_em_modo_catalogo_se_grafo_falhar() -> None:
    class _Conversations:
        async def open_or_resume(self, **kwargs):
            return CONVERSATION

        async def last_turns(self, conversation):
            return []

    class _FailingGraph:
        async def run(self, **kwargs):
            raise RuntimeError("falha inesperada")

    service = ChatService(conversations=_Conversations(), graph=_FailingGraph())  # type: ignore[arg-type]
    result = await service.handle(
        conversation_id=None,
        scope=ConversationScope(company_id=None, user_id=None),
        site_locale="pt-BR",
        content_locale="pt-BR",
        message="A loja tem capacete?",
        auth=None,
    )
    assert result is not None
    assert result.reply == catalog_mode_response(Locale.PT_BR)
    assert result.degraded is True


def test_fallback_de_produto_nao_usa_mensagem_de_erro_generica() -> None:
    assert catalog_results_response(Locale.PT_BR) == "Encontrei estas opções no catálogo:"
    assert "Não foi possível" not in catalog_mode_response(Locale.PT_BR)


async def _ids(values: set[str]) -> set[str]:
    return values


async def _bool(value: bool) -> bool:
    return value
