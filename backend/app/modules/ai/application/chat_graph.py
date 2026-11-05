"""Grafo do assistente de chat (FASE 5c) — topologia FIXA, sem loop livre.

input_guard -> route -> retrieve -> answer -> output_guard -> persist -> end.

- input_guard: gate da Fase 2 (toda mensagem + janela; 3 bloqueios = CLOSE).
- route: LLM estruturado (intent) com fallback deterministico; pedidos
  sensiveis (dados de outra empresa, desconto, alterar preco, instrucoes do
  sistema) ja caem em OFF_TOPIC/resposta neutra ANTES do LLM.
- retrieve: codigo, por intent, usando as FERRAMENTAS da Fase 5b (somente
  leitura; saida ja sanitizada/quarentenada; nunca preco). CART_HELP so para
  logado e so resumo do proprio carrinho, sem precos.
- answer: LLM curto no `reply_language` (idioma da mensagem), so com o
  contexto; devolve product_ids que sao FILTRADOS para o conjunto devolvido
  pelas ferramentas NESTE turno. `content_locale` continua separado e resolve
  apenas dados de conteudo (nome/descricao de produto).
- output_guard: guard da Fase 2 (URLs/PII/segredos/precos/idioma/canary)
  comparando com `reply_language`, nunca com o locale do site.
- persist: conversation_service (user sanitizado + assistant aprovado), audit
  sem PII e cartoes montados pelo backend.

Kill switch ou falha de LLM: resposta neutra traduzida; em PRODUCT_SEARCH os
cartoes da busca deterministica continuam (degradacao graciosa). Nenhum custo
de LLM quando AI_AGENTS_ENABLED=false.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import time
import unicodedata
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NotRequired, Protocol, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from app.core import metrics
from app.core.logging import get_logger
from app.modules.ai.application.chat_session import (
    ChatSessionState,
    ChatSessionStore,
    follow_up_decision,
    session_from_decision,
)
from app.modules.ai.application.conversation_service import ConversationService
from app.modules.ai.application.errors import LLMQueueFullError, LLMUnavailableError
from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    PriceSort,
    build_router_messages,
    deterministic_decision,
    fallback_decision,
    first_product_term,
    normalize_decision,
)
from app.modules.ai.application.knowledge import KnowledgeBase
from app.modules.ai.application.lexicon import (
    INTENT_TERMS,
    flatten,
    minimum_order_question,
    task_terms,
)
from app.modules.ai.application.ports import (
    ChatTurn,
    ConversationView,
    CurrencyConversionPort,
    LLMPort,
)
from app.modules.ai.application.product_cards import ProductCard, ProductCardService
from app.modules.ai.application.query_normalization import normalize_query
from app.modules.ai.application.security.budget import estimate_tokens
from app.modules.ai.application.security.input_gate import InputGate, InputOutcome
from app.modules.ai.application.security.prompt_builder import (
    PromptBuilder,
    load_system_prompt_template,
)
from app.modules.ai.application.tools import (
    BrandListOutput,
    BrandProductsArgs,
    BrandProductsOutput,
    CatalogOverviewArgs,
    CatalogOverviewOutput,
    CatalogTools,
    CompareProductsArgs,
    CountOutput,
    CountProductsArgs,
    GetProductArgs,
    ListBrandsArgs,
    ListCategoriesArgs,
    OrderStatusArgs,
    PriceRangeArgs,
    PriceRangeOutput,
    SearchProductsArgs,
    ShippingPolicyArgs,
    ToolOutput,
)
from app.modules.ai.domain.degradation import (
    brand_ambiguous_response,
    brand_empty_response,
    brand_list_response,
    brand_not_found_response,
    brand_products_response,
    catalog_mode_response,
    catalog_overview_response,
    catalog_results_response,
    clarify_response,
    count_products_response,
    currency_confirmation_response,
    existence_found_response,
    existence_near_response,
    existence_not_found_response,
    greeting_response,
    grounding_fallback_response,
    info_response,
    login_required_response,
    minimum_order_response,
    more_results_response,
    not_found_response,
    price_question_response,
    price_range_response,
    price_sort_response,
    price_unverified_response,
    tool_error_response,
)
from app.modules.ai.domain.language import (
    LanguageDetectorPort,
    guard_language_diverges,
    language_name,
    looks_truncated,
    max_tokens_for,
)
from app.modules.ai.domain.security.catalog_sanitizer import sanitize_tool_text
from app.modules.ai.domain.security.grounding import prices_are_grounded
from app.modules.ai.domain.security.injection import neutral_response
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import Locale, resolve_locale

ANSWER_MAX_CHARS = 600
CHAT_HISTORY_MESSAGES = 6
MAX_CONTEXT_CHARS = 3000
_logger = get_logger(__name__)
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


class ChatIntent(StrEnum):
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    SHIPPING_POLICY = "SHIPPING_POLICY"
    CATALOG_HELP = "CATALOG_HELP"
    BRAND_LIST = "BRAND_LIST"
    BRAND_PRODUCTS = "BRAND_PRODUCTS"
    CATALOG_OVERVIEW = "CATALOG_OVERVIEW"
    PRICE_RANGE = "PRICE_RANGE"
    COUNT_PRODUCTS = "COUNT_PRODUCTS"
    CART_HELP = "CART_HELP"
    ORDER_STATUS = "ORDER_STATUS"
    GREETING = "GREETING"
    INFO = "INFO"
    KNOWLEDGE = "KNOWLEDGE"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    CLARIFY = "CLARIFY"
    TOOL_ERROR = "TOOL_ERROR"
    OFF_TOPIC = "OFF_TOPIC"


class AnswerDecision(BaseModel):
    """Saida ESTRITA da resposta (ids fora do conjunto do turno sao descartados)."""

    model_config = ConfigDict(extra="forbid", strict=True)
    reply: str = Field(max_length=ANSWER_MAX_CHARS)
    product_ids: list[str] = Field(default_factory=list, max_length=6)


_SENSITIVE_TERMS = flatten(INTENT_TERMS["sensitive"])


class CartSummaryPort(Protocol):
    async def cart_summary(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str: ...


class ChatAuditPort(Protocol):
    async def record(
        self,
        *,
        company_id: uuid.UUID | None,
        event: str,
        verdict: str,
        reason_code: str,
        text: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> None: ...


@dataclass(frozen=True, kw_only=True)
class ChatRunResult:
    reply: str
    cards: list[ProductCard]
    verdict: str = "ALLOW"
    reason_code: str = "chat_turn"
    degraded: bool = False


class ChatState(TypedDict):
    conversation: ConversationView
    company_id: uuid.UUID | None
    user_id: uuid.UUID | None
    reply_language: str
    content_locale: str
    message: str
    history: list[ChatTurn]
    intent: NotRequired[ChatIntent]
    intent_decision: NotRequired[IntentDecision]
    tool_output: NotRequired[ToolOutput | None]
    context_text: NotRequired[str]
    knowledge_text: NotRequired[str]
    grounded_context: NotRequired[str]
    allowed_prices: NotRequired[frozenset[Any]]
    allowed_ids: NotRequired[set[str]]
    product_ids: NotRequired[list[str]]
    reply: NotRequired[str]
    verdict: NotRequired[str]
    reason_code: NotRequired[str]
    blocked: NotRequired[bool]
    degraded: NotRequired[bool]
    quarantined: NotRequired[list[tuple[str, str]]]
    outcome: NotRequired[ChatRunResult]
    blocked_canary: NotRequired[str]
    currency_confirmation: NotRequired[bool]
    detected_language: NotRequired[str]
    detected_confidence: NotRequired[float]
    regenerated: NotRequired[bool]
    started_at: NotRequired[float]
    router_ms: NotRequired[float]
    retrieve_ms: NotRequired[float]
    answer_ms: NotRequired[float]
    suggested_categories: NotRequired[list[str]]
    existence_not_found: NotRequired[bool]
    trusted_reply: NotRequired[bool]
    brand_list: NotRequired[BrandListOutput]
    brand_products: NotRequired[BrandProductsOutput]
    catalog_overview: NotRequired[CatalogOverviewOutput]
    price_range: NotRequired[PriceRangeOutput]
    count_products: NotRequired[CountOutput]
    _auth: NotRequired[Any]
    session: NotRequired[ChatSessionState | None]


class ChatGraph:
    def __init__(
        self,
        *,
        llm: LLMPort | None,
        tools: CatalogTools,
        cards: ProductCardService,
        input_gate: InputGate,
        conversations: ConversationService,
        cart_summary: CartSummaryPort | None,
        knowledge: KnowledgeBase | None = None,
        session_store: ChatSessionStore | None = None,
        audit: ChatAuditPort,
        ai_enabled: bool,
        history_turns: int = CHAT_HISTORY_MESSAGES,
        tag_factory: Callable[[], str] | None = None,
        language_detector: LanguageDetectorPort | None = None,
        currency_converter: CurrencyConversionPort | None = None,
        prompt_version: str = "v2",
        max_tokens_cap: int = 512,
        max_tokens_overrides: Mapping[str, int] | None = None,
        router_timeout_seconds: float = 20.0,
        answer_timeout_seconds: float = 60.0,
        regeneration_timeout_seconds: float = 20.0,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._cards = cards
        self._input_gate = input_gate
        self._conversations = conversations
        self._cart_summary = cart_summary
        self._knowledge = knowledge
        self._session_store = session_store
        self._audit = audit
        self._ai_enabled = ai_enabled
        self._history_turns = history_turns
        self._tag_factory = tag_factory or (lambda: secrets.token_hex(8))
        self._language_detector = language_detector
        self._currency_converter = currency_converter
        self._prompt_version = prompt_version
        self._max_tokens_cap = max_tokens_cap
        self._max_tokens_overrides = dict(max_tokens_overrides or {})
        self._router_timeout_seconds = max(1.0, float(router_timeout_seconds))
        self._answer_timeout_seconds = max(1.0, float(answer_timeout_seconds))
        self._regeneration_timeout_seconds = max(1.0, float(regeneration_timeout_seconds))
        self._system_template = load_system_prompt_template(prompt_version)
        self._graph = self._build()

    def _build(self) -> Any:
        graph: StateGraph[ChatState] = StateGraph(ChatState)
        graph.add_node("input_guard", self._input_guard)
        graph.add_node("route", self._route)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("answer", self._answer)
        graph.add_node("output_guard", self._output_guard)
        graph.add_node("persist", self._persist)
        graph.set_entry_point("input_guard")
        graph.add_conditional_edges(
            "input_guard", self._after_guard, {"route": "route", "persist": "persist"}
        )
        graph.add_edge("route", "retrieve")
        graph.add_edge("retrieve", "answer")
        graph.add_edge("answer", "output_guard")
        graph.add_edge("output_guard", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    async def run(
        self,
        *,
        conversation: ConversationView,
        reply_language: str,
        message: str,
        history: Sequence[ChatTurn],
        auth: Any,
        content_locale: str | None = None,
    ) -> ChatRunResult:
        session = (
            await self._session_store.load(conversation.id)
            if self._session_store is not None
            else None
        )
        state = await self._graph.ainvoke(
            {
                "conversation": conversation,
                "session": session,
                "company_id": conversation.company_id,
                "user_id": conversation.user_id,
                "reply_language": reply_language,
                "content_locale": content_locale or reply_language,
                "message": message,
                "history": list(history),
                "started_at": time.perf_counter(),
                "_auth": auth,
            }
        )
        outcome = state.get("outcome")
        if not isinstance(outcome, ChatRunResult):  # pragma: no cover
            raise RuntimeError("chat sem outcome")
        return outcome

    # ------------------------------------------------------------------ nodes
    async def _input_guard(self, state: ChatState) -> dict[str, Any]:
        decision = self._input_gate.check(
            conversation_id=state["conversation"].id,
            locale=resolve_locale(state["reply_language"]),
            raw_message=state["message"],
            recent_user_messages=[turn.content for turn in state["history"] if turn.role == "user"],
        )
        if decision.outcome in (InputOutcome.BLOCK, InputOutcome.CLOSE):
            metrics.increment_ai_guard_block(agent="chat")
            return {
                "blocked": True,
                "verdict": "BLOCK",
                "reason_code": decision.reason_code or "input_blocked",
                "reply": neutral_response(resolve_locale(state["reply_language"])),
                "product_ids": [],
                "allowed_ids": set(),
                "context_text": "",
            }
        return {"message": decision.text or state["message"]}

    def _after_guard(self, state: ChatState) -> str:
        return "persist" if state.get("blocked") else "route"

    async def _route(self, state: ChatState) -> dict[str, Any]:
        lowered = state["message"].lower()
        if any(term in lowered for term in _SENSITIVE_TERMS):
            return {
                "intent": ChatIntent.OFF_TOPIC,
                "intent_decision": IntentDecision(
                    intent=IntentName.OUT_OF_SCOPE, language=state["reply_language"]
                ),
                "reason_code": "sensitive_request",
            }
        session = state.get("session")
        follow_up = (
            follow_up_decision(session, state["message"], reply_language=state["reply_language"])
            if session is not None
            else None
        )
        if follow_up is not None:
            return {
                "intent": _map_intent(follow_up.intent),
                "intent_decision": follow_up,
                "reason_code": ("follow_up_more" if follow_up.offset > 0 else "follow_up"),
            }
        # 1) atalhos de codigo (preco/produto/frete/etc.) SEM LLM; 2) LLM
        # curto para o que restar; 3) product_search com o texto original.
        decision = deterministic_decision(state["message"], reply_language=state["reply_language"])
        if decision is not None and decision.availability_check:
            return {
                "intent": ChatIntent.PRODUCT_SEARCH,
                "intent_decision": decision,
                "reason_code": "existence_check",
            }
        reason_code = "keyword_route" if decision is not None else "intent_llm"
        needs_refs = (
            decision is not None
            and decision.intent
            in (
                IntentName.PRODUCT_COMPARE,
                IntentName.PRODUCT_DETAIL,
                IntentName.AVAILABILITY,
                IntentName.ORDER_STATUS,
            )
            and not decision.product_refs
        )
        if decision is None or needs_refs:
            refined = await self._ask_intent(state)
            if refined is not None:
                if decision is None:
                    decision = refined
                else:
                    # Mantem a intent deterministica (compare/detail/estoque)
                    # e aproveita apenas as referencias extraidas pelo LLM.
                    decision = decision.model_copy(
                        update={
                            "product_refs": refined.product_refs,
                            "query": refined.query or decision.query,
                        }
                    )
        if decision is None:
            decision = fallback_decision(state["message"], reply_language=state["reply_language"])
            reason_code = "intent_fallback"
        return {
            "intent": _map_intent(decision.intent),
            "intent_decision": decision,
            "reason_code": reason_code,
        }

    async def _ask_intent(self, state: ChatState) -> IntentDecision | None:
        if not self._ai_enabled or self._llm is None:
            return None
        messages = build_router_messages(
            message=state["message"],
            history=state["history"],
            reply_language=state["reply_language"],
            tag=self._tag(),
        )
        started = time.perf_counter()
        try:
            decision = await asyncio.wait_for(
                self._llm.complete_structured(
                    schema=IntentDecision,
                    messages=messages,
                    temperature=0.1,
                ),
                timeout=self._router_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - fallback deterministico
            state["router_ms"] = round((time.perf_counter() - started) * 1000, 1)
            _log_llm_failure("router", exc)
            metrics.observe_llm_call(
                agent="chat",
                duration=time.perf_counter() - started,
                outcome="error",
                estimated_tokens=estimate_tokens(len(state["message"])),
            )
            return None
        state["router_ms"] = round((time.perf_counter() - started) * 1000, 1)
        metrics.observe_llm_call(
            agent="chat",
            duration=time.perf_counter() - started,
            outcome="ok",
            estimated_tokens=estimate_tokens(len(state["message"])),
        )
        return normalize_decision(
            decision, message=state["message"], reply_language=state["reply_language"]
        )

    async def _retrieve(self, state: ChatState) -> dict[str, Any]:
        """Executa ferramentas; qualquer falha vira mensagem amigavel (sem 500)."""
        started = time.perf_counter()
        try:
            result = await self._retrieve_inner(state)
            state["retrieve_ms"] = round((time.perf_counter() - started) * 1000, 1)
            return _with_grounded(result)
        except Exception:
            state["retrieve_ms"] = round((time.perf_counter() - started) * 1000, 1)
            _logger.exception(
                "chat_tool_failed",
                intent=state.get("intent", ""),
                message_chars=len(state.get("message", "")),
            )
            return {
                "intent": ChatIntent.TOOL_ERROR,
                "tool_output": None,
                "context_text": "",
                "allowed_ids": set(),
                "quarantined": [],
                "reason_code": "tool_error",
            }

    async def _retrieve_inner(  # noqa: C901 - despacho por intencao
        self, state: ChatState
    ) -> dict[str, Any]:
        intent = state["intent"]
        auth = state.get("_auth")
        special = self._special_retrieve(state)
        if special is not None:
            return special
        decision = state.get("intent_decision") or fallback_decision(
            state["message"], reply_language=state["reply_language"]
        )
        converted_decision = await self._convert_currency(decision)
        if converted_decision is None:
            return {
                "currency_confirmation": True,
                "tool_output": None,
                "context_text": "",
                "allowed_ids": set(),
                "quarantined": [],
                "reason_code": "currency_confirmation",
            }
        decision = converted_decision
        state["intent_decision"] = decision
        query = _query_for(decision, state["message"])
        if decision.availability_check:
            return await self._existence_retrieve(decision, query=query, state=state, auth=auth)
        if intent == ChatIntent.ORDER_STATUS:
            return await self._order_retrieve(state, decision, auth)
        if intent == ChatIntent.CART_HELP:
            return await self._cart_retrieve(state)
        if intent == ChatIntent.SHIPPING_POLICY:
            return self._shipping_retrieve(state)
        if intent == ChatIntent.CATALOG_HELP:
            return await self._catalog_retrieve(state)
        if intent == ChatIntent.CATALOG_OVERVIEW:
            return await self._overview_retrieve(decision, state)
        if intent == ChatIntent.BRAND_LIST:
            return await self._brand_list_retrieve(decision, state, auth)
        if intent == ChatIntent.BRAND_PRODUCTS:
            return await self._brand_products_retrieve(decision, state, auth)
        if intent == ChatIntent.PRICE_RANGE:
            return await self._price_range_retrieve(decision, state, auth)
        if intent == ChatIntent.COUNT_PRODUCTS:
            return await self._count_retrieve(decision, state, auth)
        return await self._product_dispatch(decision, query=query, state=state, auth=auth)

    async def _convert_currency(self, decision: IntentDecision) -> IntentDecision | None:
        """Converte filtros em moeda de exibicao para BRL; None = confirmar.

        Moeda fora da lista suportada, cambio indisponivel ou valor misto NUNCA
        viram filtro em BRL: o grafo pede UMA confirmacao objetiva.
        """
        if decision.price_currency_confirmation:
            return None
        has_price = decision.price_min is not None or decision.price_max is not None
        if not has_price or decision.price_currency == "BRL":
            return decision
        converter = self._currency_converter
        if converter is None or decision.price_currency not in converter.supported:
            return None
        price_min = decision.price_min
        price_max = decision.price_max
        if price_min is not None:
            converted_min = await converter.to_brl(
                float(price_min), currency=decision.price_currency
            )
            if converted_min is None:
                return None
            price_min = round(converted_min, 2)
        if price_max is not None:
            converted_max = await converter.to_brl(
                float(price_max), currency=decision.price_currency
            )
            if converted_max is None:
                return None
            price_max = round(converted_max, 2)
        return decision.model_copy(
            update={
                "price_min": price_min,
                "price_max": price_max,
                "price_currency": "BRL",
                "price_currency_confirmation": False,
            }
        )

    async def _search_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        limit = _requested_limit(decision)
        args: dict[str, Any] = {
            "query": query[:200],
            "query_pt": decision.query_pt[:200],
            "query_en": decision.query_en[:200],
            "limit": limit,
            "price_sort": decision.price_sort.value if decision.price_sort else None,
            "price_min": float(decision.price_min) if decision.price_min is not None else None,
            "price_max": float(decision.price_max) if decision.price_max is not None else None,
            "brand": decision.brand,
            "attributes": decision.attributes,
            "offset": decision.offset,
        }
        try:
            search_args = SearchProductsArgs.model_validate(args)
        except Exception:  # noqa: BLE001 - filtro invalido do LLM
            search_args = SearchProductsArgs.model_validate({"query": query[:200], "limit": 5})
        output = await self._tools.search_products(
            search_args, locale=state["content_locale"], auth=auth
        )
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    async def _existence_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        """Busca de existencia: exata e, se vazio, sinonimos/trigram.

        Nao chama LLM. Se nada existir, devolve categorias reais do catalogo
        para a resposta deterministica de "nao encontrei".
        """
        exact = await self._search_retrieve(decision, query=query, state=state, auth=auth)
        output = exact.get("tool_output")
        if isinstance(output, ToolOutput) and output.product_ids:
            return exact
        near_outputs: list[ToolOutput] = []
        for near in _near_queries(query):
            try:
                near_outputs.append(
                    await self._tools.search_products(
                        SearchProductsArgs.model_validate({"query": near[:200], "limit": 3}),
                        locale=state["content_locale"],
                        auth=auth,
                    )
                )
            except Exception:  # noqa: BLE001 - sugestao nunca derruba a resposta
                _logger.warning("chat_existence_near_failed", query_chars=len(near))
        merged = _merge_tool_outputs(near_outputs, limit=5)
        if merged.product_ids:
            return {
                "tool_output": merged,
                "context_text": merged.context_text[:MAX_CONTEXT_CHARS],
                "allowed_ids": set(merged.product_ids),
                "quarantined": _quarantine(merged),
                "existence_not_found": True,
                "suggested_categories": [],
            }
        categories_output = await self._tools.list_categories(
            ListCategoriesArgs(), locale=state["content_locale"]
        )
        return {
            "tool_output": None,
            "context_text": "",
            "allowed_ids": set(),
            "quarantined": _quarantine(categories_output),
            "existence_not_found": True,
            "suggested_categories": _category_names(categories_output.context_text),
        }

    def _shipping_retrieve(self, state: ChatState) -> dict[str, Any]:
        output = self._tools.get_shipping_policy(
            ShippingPolicyArgs(), locale=state["reply_language"]
        )
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    async def _catalog_retrieve(self, state: ChatState) -> dict[str, Any]:
        overview = await self._tools.overview(
            CatalogOverviewArgs(), locale=state["content_locale"]
        )
        return {
            "catalog_overview": overview,
            "tool_output": None,
            "context_text": "",
            "allowed_ids": set(),
            "quarantined": [],
        }

    async def _overview_retrieve(
        self, decision: IntentDecision, state: ChatState
    ) -> dict[str, Any]:
        overview = await self._tools.overview(
            CatalogOverviewArgs(category_query=decision.query or None),
            locale=state["content_locale"],
        )
        return {
            "catalog_overview": overview,
            "tool_output": None,
            "context_text": "",
            "allowed_ids": set(),
            "quarantined": [],
            "reason_code": "catalog_overview",
        }

    async def _brand_list_retrieve(
        self, decision: IntentDecision, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        result = await self._tools.list_brands(
            ListBrandsArgs(
                category=decision.category,
                query=decision.query or None,
                limit=20,
            ),
            locale=state["content_locale"],
            auth=auth,
        )
        return {
            "brand_list": result,
            "tool_output": None,
            "context_text": "",
            "allowed_ids": set(),
            "quarantined": [],
            "reason_code": "brand_list",
        }

    async def _brand_products_retrieve(
        self, decision: IntentDecision, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        result = await self._tools.brand_products(
            BrandProductsArgs(
                brand=decision.brand or decision.query or "",
                category=decision.category,
                sort=decision.price_sort.value if decision.price_sort else None,
            ),
            locale=state["content_locale"],
            auth=auth,
        )
        if result.brand is not None:
            state["intent_decision"] = decision.model_copy(
                update={"brand": result.brand.name, "query": ""}
            )
        payload: dict[str, Any] = {
            "brand_products": result,
            "tool_output": result.tool_output,
            "context_text": (
                result.tool_output.context_text[:MAX_CONTEXT_CHARS]
                if result.tool_output is not None
                else ""
            ),
            "allowed_ids": (
                set(result.tool_output.product_ids)
                if result.tool_output is not None
                else set()
            ),
            "quarantined": (
                _quarantine(result.tool_output)
                if result.tool_output is not None
                else []
            ),
            "reason_code": result.reason_code or "brand_products",
        }
        return payload

    async def _price_range_retrieve(
        self, decision: IntentDecision, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        result = await self._tools.price_range(
            PriceRangeArgs(category=decision.category, query=decision.query or None),
            locale=state["content_locale"],
            auth=auth,
        )
        return {
            "price_range": result,
            "tool_output": result.tool_output,
            "context_text": (
                result.tool_output.context_text[:MAX_CONTEXT_CHARS]
                if result.tool_output is not None
                else ""
            ),
            "allowed_ids": (
                set(result.tool_output.product_ids)
                if result.tool_output is not None
                else set()
            ),
            "quarantined": (
                _quarantine(result.tool_output)
                if result.tool_output is not None
                else []
            ),
            "reason_code": "price_range",
        }

    async def _count_retrieve(
        self, decision: IntentDecision, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        result = await self._tools.count_products(
            CountProductsArgs(
                category=decision.category,
                brand=decision.brand,
                query=decision.query or None,
            ),
            locale=state["content_locale"],
            auth=auth,
        )
        return {
            "count_products": result,
            "tool_output": None,
            "context_text": "",
            "allowed_ids": set(),
            "quarantined": [],
            "reason_code": "count_products",
        }

    async def _order_retrieve(
        self, state: ChatState, decision: IntentDecision, auth: Any
    ) -> dict[str, Any]:
        if auth is None:
            return _login_required_state("order_requires_login")
        if not decision.product_refs:
            return _clarify_state("order_id_required")
        output = await self._tools.get_order_status(
            OrderStatusArgs(order_id=decision.product_refs[0]), auth=auth
        )
        if output.reason_code == "order_not_found":
            return _not_found_state("order_not_found")
        if output.reason_code == "login_required":
            return _login_required_state("order_requires_login")
        if output.reason_code or not output.context_text:
            return _tool_error_state(output.reason_code or "order_empty")
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(),
            "quarantined": _quarantine(output),
        }

    async def _cart_retrieve(self, state: ChatState) -> dict[str, Any]:
        company_id, user_id = state.get("company_id"), state.get("user_id")
        if (
            state.get("_auth") is None
            or company_id is None
            or user_id is None
            or self._cart_summary is None
        ):
            return _login_required_state("cart_requires_login")
        summary = await self._cart_summary.cart_summary(company_id=company_id, user_id=user_id)
        doc = sanitize_tool_text(summary, label="carrinho_do_usuario", max_chars=600)
        if doc.quarantined or not doc.context_text:
            return _tool_error_state("cart_sanitized")
        return {
            "tool_output": None,
            "context_text": doc.context_text,
            "allowed_ids": set(),
            "quarantined": [],
        }

    async def _product_dispatch(
        self,
        decision: IntentDecision,
        *,
        query: str,
        state: ChatState,
        auth: Any,
    ) -> dict[str, Any]:
        if decision.task:
            return await self._consultation_retrieve(decision, query=query, state=state)
        if decision.intent == IntentName.PRODUCT_COMPARE:
            return await self._compare_retrieve(decision, query=query, state=state)
        if decision.intent in (IntentName.PRODUCT_DETAIL, IntentName.AVAILABILITY):
            return await self._detail_retrieve(decision, query=query, state=state)
        return await self._search_retrieve(decision, query=query, state=state, auth=auth)

    def _special_retrieve(self, state: ChatState) -> dict[str, Any] | None:
        if state["intent"] in (
            ChatIntent.OFF_TOPIC,
            ChatIntent.GREETING,
            ChatIntent.INFO,
        ):
            return {
                "tool_output": None,
                "context_text": "",
                "allowed_ids": set(),
                "quarantined": [],
            }
        if state["intent"] == ChatIntent.KNOWLEDGE:
            return self._knowledge_retrieve(state)
        return None

    def _knowledge_retrieve(self, state: ChatState) -> dict[str, Any]:
        if self._knowledge is None:
            return _base_state(ChatIntent.INFO, "knowledge_unavailable")
        decision = state.get("intent_decision")
        sections = self._knowledge.search(
            state["message"],
            limit=2,
            task=decision.task if decision is not None else None,
        )
        if not sections:
            return _base_state(ChatIntent.INFO, "knowledge_not_found")
        text = "\n\n".join(f"{section.title}:\n{section.text}" for section in sections)
        return {
            "tool_output": None,
            "context_text": text[:MAX_CONTEXT_CHARS],
            "knowledge_text": text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(),
            "quarantined": [],
        }

    async def _consultation_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState
    ) -> dict[str, Any]:
        sections = (
            self._knowledge.search(
                _consultation_query(decision, query), limit=2, task=decision.task
            )
            if self._knowledge is not None
            else ()
        )
        attempts = _consultation_attempts(sections, decision, query)
        max_products = _requested_limit(decision)
        outputs: list[ToolOutput] = []
        for term, category in attempts:
            output = await self._search_with_optional_category(
                decision,
                query=term,
                category=category,
                state=state,
                limit=min(2, max_products),
            )
            if output.product_ids:
                outputs.append(output)
            if sum(len(item.grounded) for item in outputs) >= max_products:
                break
        merged = _merge_tool_outputs(outputs, limit=max_products)
        if not merged.product_ids:
            # Alternativa mais proxima: busca simples pela tarefa, sem categoria.
            merged = await self._search_with_optional_category(
                decision,
                query=decision.task or query,
                category=None,
                state=state,
            )
        knowledge_text = "\n\n".join(f"{section.title}:\n{section.text}" for section in sections)[
            :MAX_CONTEXT_CHARS
        ]
        return {
            "tool_output": merged,
            "context_text": merged.context_text[:MAX_CONTEXT_CHARS],
            "knowledge_text": knowledge_text,
            "allowed_ids": set(merged.product_ids),
            "quarantined": _quarantine(merged),
        }

    async def _search_with_optional_category(
        self,
        decision: IntentDecision,
        *,
        query: str,
        category: str | None,
        state: ChatState,
        limit: int | None = None,
    ) -> ToolOutput:
        limit = limit or _requested_limit(decision)
        args: dict[str, Any] = {
            "query": query[:200],
            "query_pt": decision.query_pt[:200],
            "query_en": decision.query_en[:200],
            "limit": limit,
            "category": category,
            "price_sort": decision.price_sort.value if decision.price_sort else None,
            "price_min": float(decision.price_min) if decision.price_min is not None else None,
            "price_max": float(decision.price_max) if decision.price_max is not None else None,
            "brand": decision.brand,
            "attributes": decision.attributes,
            "offset": decision.offset,
        }
        try:
            search_args = SearchProductsArgs.model_validate(args)
        except Exception:  # noqa: BLE001 - categoria/filtro invalido do LLM
            search_args = SearchProductsArgs.model_validate({"query": query[:200], "limit": 5})
        return await self._tools.search_products(
            search_args, locale=state["content_locale"], auth=state.get("_auth")
        )

    async def _compare_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState
    ) -> dict[str, Any]:
        refs = list(decision.product_refs)
        if len(refs) < 2:
            nearest = await self._tools.search_products(
                SearchProductsArgs.model_validate(
                    {
                        "query": query[:200],
                        "query_pt": decision.query_pt,
                        "query_en": decision.query_en,
                        "limit": 2,
                    }
                ),
                locale=state["content_locale"],
                auth=state.get("_auth"),
            )
            refs = list(nearest.product_ids)
        if len(refs) < 2:
            return _clarify_state("compare_needs_two")
        output = await self._tools.compare_products(
            CompareProductsArgs(product_refs=refs[:4]),
            locale=state["content_locale"],
            auth=state.get("_auth"),
        )
        if output.reason_code == "compare_needs_two":
            return {
                **_clarify_state("compare_needs_two"),
                "allowed_ids": set(output.product_ids),
                "quarantined": _quarantine(output),
            }
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    async def _detail_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState
    ) -> dict[str, Any]:
        ref = decision.product_refs[0] if decision.product_refs else None
        if ref is None:
            nearest = await self._tools.search_products(
                SearchProductsArgs.model_validate(
                    {
                        "query": query[:200],
                        "query_pt": decision.query_pt,
                        "query_en": decision.query_en,
                        "limit": 1,
                    }
                ),
                locale=state["content_locale"],
                auth=state.get("_auth"),
            )
            ref = nearest.product_ids[0] if nearest.product_ids else None
        if ref is None:
            return _clarify_state("product_not_provided")
        output = await self._tools.get_product(
            GetProductArgs(product_ref=ref),
            locale=state["content_locale"],
            auth=state.get("_auth"),
        )
        if output.reason_code == "product_not_found":
            return _clarify_state("product_not_found")
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    def _direct_answer(  # noqa: C901 - atalhos deterministicos por intencao
        self, state: ChatState, locale: Any
    ) -> dict[str, Any] | None:
        """Respostas de codigo (sem LLM): estado, saudacao, frete e preco."""
        decision = state.get("intent_decision")
        if decision is not None and decision.availability_check:
            ordered_ids = _ordered_ids(state)
            if state.get("existence_not_found"):
                if ordered_ids:
                    return {
                        "reply": existence_near_response(locale),
                        "product_ids": ordered_ids[:5],
                        "trusted_reply": True,
                    }
                return {
                    "reply": existence_not_found_response(
                        locale, categories=tuple(state.get("suggested_categories", []))
                    ),
                    "product_ids": [],
                    "trusted_reply": True,
                }
            if ordered_ids:
                return {
                    "reply": existence_found_response(locale),
                    "product_ids": ordered_ids[:5],
                    "trusted_reply": True,
                }
            return {
                "reply": existence_not_found_response(
                    locale, categories=tuple(state.get("suggested_categories", []))
                ),
                "product_ids": [],
                "trusted_reply": True,
            }
        if (
            decision is not None
            and decision.offset > 0
            and state["intent"] == ChatIntent.PRODUCT_SEARCH
            and _ordered_ids(state)
        ):
            return {
                "reply": more_results_response(locale),
                "product_ids": _ordered_ids(state)[:5],
                "trusted_reply": True,
            }
        if state["intent"] == ChatIntent.BRAND_LIST:
            brand_list_data = state.get("brand_list")
            if brand_list_data is not None:
                return {
                    "reply": brand_list_response(
                        locale,
                        brands=tuple(
                            (brand.name, brand.count) for brand in brand_list_data.brands
                        ),
                        total=brand_list_data.total,
                        query=brand_list_data.query,
                    ),
                    "product_ids": [],
                    "trusted_reply": True,
                }
        if state["intent"] == ChatIntent.BRAND_PRODUCTS:
            brand_products_data = state.get("brand_products")
            if brand_products_data is not None:
                if brand_products_data.reason_code == "brand_ambiguous":
                    return {
                        "reply": brand_ambiguous_response(
                            locale,
                            brand=state["intent_decision"].brand or "",
                            candidates=tuple(
                                candidate.name
                                for candidate in brand_products_data.candidates
                            ),
                        ),
                        "product_ids": [],
                        "trusted_reply": True,
                    }
                if (
                    brand_products_data.reason_code == "brand_not_found"
                    or brand_products_data.brand is None
                ):
                    return {
                        "reply": brand_not_found_response(
                            locale,
                            brand=state["intent_decision"].brand or "",
                            available=brand_products_data.available,
                        ),
                        "product_ids": [],
                        "trusted_reply": True,
                    }
                if brand_products_data.tool_output is None:
                    return {
                        "reply": brand_empty_response(
                            locale, brand=brand_products_data.brand.name
                        ),
                        "product_ids": [],
                        "trusted_reply": True,
                    }
                return {
                    "reply": brand_products_response(
                        locale, brand=brand_products_data.brand.name
                    ),
                    "product_ids": list(brand_products_data.tool_output.product_ids)[:5],
                    "trusted_reply": True,
                }
        if state["intent"] in (ChatIntent.CATALOG_HELP, ChatIntent.CATALOG_OVERVIEW):
            overview_data = state.get("catalog_overview")
            if overview_data is not None:
                return {
                    "reply": catalog_overview_response(
                        locale,
                        total_products=overview_data.total_products,
                        categories=tuple(
                            (category.name, category.count)
                            for category in overview_data.categories
                        ),
                        category_query=overview_data.category_query,
                    ),
                    "product_ids": [],
                    "trusted_reply": True,
                }
        if state["intent"] == ChatIntent.PRICE_RANGE:
            price_data = state.get("price_range")
            if price_data is not None:
                product_ids = (
                    list(price_data.tool_output.product_ids)[:2]
                    if price_data.tool_output is not None
                    else []
                )
                return {
                    "reply": price_range_response(
                        locale,
                        query=state["intent_decision"].query or None,
                        minimum=price_data.min_price,
                        maximum=price_data.max_price,
                        count=price_data.count,
                    ),
                    "product_ids": product_ids,
                    "trusted_reply": True,
                }
        if state["intent"] == ChatIntent.COUNT_PRODUCTS:
            count_data = state.get("count_products")
            if count_data is not None:
                decision = state.get("intent_decision")
                return {
                    "reply": count_products_response(
                        locale,
                        total=count_data.total,
                        query=decision.query if decision is not None else None,
                        brand=decision.brand if decision is not None else None,
                        category=decision.category if decision is not None else None,
                    ),
                    "product_ids": [],
                    "trusted_reply": True,
                }
        if (
            decision is not None
            and decision.intent == IntentName.POLICY_FAQ
            and minimum_order_question(state["message"])
        ):
            return {"reply": minimum_order_response(locale), "product_ids": []}
        text_fn = _DIRECT_TEXT.get(state["intent"])
        if text_fn is not None:
            return {"reply": text_fn(locale), "product_ids": []}
        if state["intent"] == ChatIntent.CLARIFY:
            return {
                "reply": clarify_response(locale),
                "product_ids": _ordered_ids(state)[:5],
            }
        if state["intent"] == ChatIntent.SHIPPING_POLICY:
            policy = (state.get("context_text") or "").strip()
            if policy:
                return {"reply": policy, "product_ids": []}
        return self._price_direct_answer(state, locale)

    def _price_direct_answer(self, state: ChatState, locale: Any) -> dict[str, Any] | None:
        """Preco: o VALOR fica no cartao; o texto e deterministico e localizado."""
        decision = state.get("intent_decision")
        ordered_ids = _ordered_ids(state)
        if decision is None or not ordered_ids:
            return None
        name = _first_product_name(state.get("context_text", ""))
        if not name:
            return None
        if decision.intent == IntentName.PRICE_QUESTION:
            return {
                "reply": price_question_response(locale, name=name, visitor=False),
                "product_ids": ordered_ids[:5],
            }
        if decision.price_sort in (PriceSort.ASC, PriceSort.DESC):
            output = state.get("tool_output")
            capped = bool(output.price_scan_capped) if output is not None else False
            return {
                "reply": price_sort_response(
                    locale,
                    name=name,
                    visitor=False,
                    capped=capped,
                    direction="desc" if decision.price_sort == PriceSort.DESC else "asc",
                ),
                "product_ids": ordered_ids[:5],
            }
        return None

    def _currency_confirmation_reply(
        self, state: ChatState, locale: Locale
    ) -> dict[str, Any] | None:
        if not state.get("currency_confirmation"):
            return None
        decision = state.get("intent_decision")
        return {
            "reply": currency_confirmation_response(
                locale,
                minimum=decision.price_min if decision is not None else None,
                maximum=decision.price_max if decision is not None else None,
                currency=decision.price_currency if decision is not None else "BRL",
            ),
            "product_ids": [],
        }

    async def _answer(self, state: ChatState) -> dict[str, Any]:  # noqa: C901 - fluxo de resposta
        if state.get("blocked"):
            return {}
        locale = resolve_locale(state["reply_language"])
        confirmation = self._currency_confirmation_reply(state, locale)
        if confirmation is not None:
            return confirmation
        direct = self._direct_answer(state, locale)
        if direct is not None:
            return direct
        allowed = set(state.get("allowed_ids", set()))
        allowed_prices = frozenset(state.get("allowed_prices", frozenset()))
        ordered_ids = _ordered_ids(state)
        decision = state.get("intent_decision")
        fallback = self._deterministic_answer(state, locale)
        llm_fallback = {
            "reply": (
                catalog_results_response(locale)
                if ordered_ids and state["intent"] == ChatIntent.PRODUCT_SEARCH
                else catalog_mode_response(locale)
            ),
            "product_ids": (
                ordered_ids[:5] if state["intent"] == ChatIntent.PRODUCT_SEARCH else []
            ),
            "degraded": True,
        }
        if not self._ai_enabled or self._llm is None:
            return llm_fallback
        canary = secrets.token_hex(8)
        builder = PromptBuilder(canary_token=canary, prompt_version=self._prompt_version)
        # Contexto curto: ultimas N mensagens (o servico tambem trunca) e
        # trechos de catalogo limitados. O modelo local tem janela pequena.
        history = state["history"][-self._history_turns :]
        messages = builder.build(
            locale=locale,
            user_message=state["message"],
            history=[(turn.role, turn.content) for turn in history],
            tool_context=_answer_context(state) or None,
        )
        # Qwen (template do LM Studio) exige UM system message no INICIO:
        # concatenar a instrucao extra no system existente, nunca inserir outro.
        extra_system = _answer_instruction(decision)
        messages[0] = {
            "role": "system",
            "content": f"{messages[0]['content']}\n\n{extra_system}",
        }
        limit = self._token_limit(locale)
        started = time.perf_counter()
        try:
            answer = await asyncio.wait_for(
                self._llm.complete_structured(
                    schema=AnswerDecision, messages=messages, max_tokens=limit
                ),
                timeout=self._answer_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - tenta UMA regeneracao curta
            _log_llm_failure("answer", exc)
            metrics.observe_llm_call(
                agent="chat",
                duration=time.perf_counter() - started,
                outcome="error",
                estimated_tokens=estimate_tokens(
                    len(state["message"]) + len(state.get("context_text", ""))
                ),
            )
            regenerated = await self._regenerate_answer(messages, locale, limit, reason="truncated")
            if regenerated is None:
                state["answer_ms"] = round((time.perf_counter() - started) * 1000, 1)
                return llm_fallback
            answer = regenerated
        state["answer_ms"] = round((time.perf_counter() - started) * 1000, 1)
        metrics.observe_llm_call(
            agent="chat",
            duration=time.perf_counter() - started,
            outcome="ok",
            estimated_tokens=estimate_tokens(
                len(state["message"]) + len(state.get("context_text", ""))
            ),
        )
        repaired = await self._maybe_repair(
            answer,
            messages,
            allowed=allowed,
            allowed_prices=allowed_prices,
            knowledge_text=state.get("knowledge_text", ""),
            state=state,
            ordered_ids=ordered_ids,
            canary=canary,
            locale=locale,
        )
        if isinstance(repaired, dict):
            return repaired
        answer = repaired
        if looks_truncated(answer.reply, locale):
            state["regenerated"] = True
            regenerated = await self._regenerate_answer(messages, locale, limit, reason="truncated")
            if regenerated is None or looks_truncated(regenerated.reply, locale):
                return fallback
            answer = regenerated
            if (
                _grounded_problem(
                    answer,
                    allowed,
                    allowed_prices,
                    knowledge_text=state.get("knowledge_text", ""),
                )
                is not None
            ):
                return fallback
        detected = self._detect_reply(answer.reply)
        if detected is not None:
            state["detected_language"] = (
                detected.language.value if detected.language is not None else ""
            )
            state["detected_confidence"] = detected.confidence
        if self._reply_diverges(answer.reply, locale):
            state["regenerated"] = True
            regenerated = await self._regenerate_answer(messages, locale, limit, reason="language")
            if regenerated is None or self._reply_diverges(regenerated.reply, locale):
                return fallback
            answer = regenerated
            if (
                _grounded_problem(
                    answer,
                    allowed,
                    allowed_prices,
                    knowledge_text=state.get("knowledge_text", ""),
                )
                is not None
            ):
                return fallback
        valid_ids = [pid for pid in answer.product_ids if pid in allowed]
        # Os cartoes sao SEMPRE montados a partir dos produtos retornados
        # nesta rodada, independentemente do texto do LLM.
        if ordered_ids and state["intent"] == ChatIntent.PRODUCT_SEARCH:
            valid_ids = ordered_ids[:5]
        # Anti-alucinacao: em produto, UUID citado que NAO veio das ferramentas
        # deste turno e removido. Pedido/KB preservam seus UUIDs legitimos.
        reply = (
            _filter_unknown_ids(answer.reply, allowed)
            if state["intent"] == ChatIntent.PRODUCT_SEARCH
            else answer.reply
        )
        if not reply:
            return fallback
        return {"reply": reply, "product_ids": valid_ids, "blocked_canary": canary}

    def _token_limit(self, locale: Locale) -> int:
        override = self._max_tokens_overrides.get(locale.value)
        limit = override or max_tokens_for(locale, cap=self._max_tokens_cap)
        return max(16, min(int(limit), self._max_tokens_cap))

    def _detect_reply(self, text: str) -> Any | None:
        if self._language_detector is None:
            return None
        return self._language_detector.detect(text)

    def _reply_diverges(self, text: str, locale: Locale) -> bool:
        if self._language_detector is None:
            return False
        return guard_language_diverges(text, expected=locale, detector=self._language_detector)

    def _deterministic_answer(self, state: ChatState, locale: Locale) -> dict[str, Any]:
        ordered_ids = _ordered_ids(state)
        if state["intent"] == ChatIntent.PRODUCT_SEARCH and ordered_ids:
            return {
                "reply": catalog_results_response(locale),
                "product_ids": ordered_ids[:5],
                "degraded": True,
                "trusted_reply": True,
            }
        return {
            "reply": catalog_mode_response(locale),
            "product_ids": [],
            "degraded": True,
            "trusted_reply": True,
        }

    async def _regenerate_answer(
        self,
        messages: Sequence[Any],
        locale: Locale,
        limit: int,
        *,
        reason: str,
    ) -> AnswerDecision | None:
        if self._llm is None:
            return None
        if reason == "language":
            instruction = (
                f"Your previous answer was NOT in {language_name(locale)}. "
                f"Reply again ONLY in {language_name(locale)}, 1 to 2 short "
                "sentences, using the same CONTEXT and the JSON schema."
            )
        else:
            instruction = (
                "Your previous answer was cut off or invalid. Reply again in "
                "at most 2 short sentences, finish every sentence, use the same "
                "CONTEXT and the JSON schema."
            )
        try:
            return await asyncio.wait_for(
                self._llm.complete_structured(
                    schema=AnswerDecision,
                    messages=[*messages, {"role": "user", "content": instruction}],
                    temperature=0.1,
                    max_tokens=limit,
                ),
                timeout=self._regeneration_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - fallback deterministico
            _log_llm_failure(f"regeneration_{reason}", exc)
            return None

    async def _maybe_repair(
        self,
        answer: AnswerDecision,
        messages: Sequence[Any],
        *,
        allowed: set[str],
        allowed_prices: frozenset[Any],
        knowledge_text: str,
        state: ChatState,
        ordered_ids: list[str],
        canary: str,
        locale: Any,
    ) -> AnswerDecision | dict[str, Any]:
        problem = _grounded_problem(answer, allowed, allowed_prices, knowledge_text=knowledge_text)
        if problem is None:
            return answer
        repaired = await self._repair_answer(messages, problem=problem, locale=locale)
        if (
            repaired is not None
            and _grounded_problem(repaired, allowed, allowed_prices, knowledge_text=knowledge_text)
            is None
        ):
            return repaired
        _logger.warning(
            "chat_grounding_fallback",
            problem=problem,
            intent=state.get("intent", "UNKNOWN"),
        )
        product_search = state["intent"] == ChatIntent.PRODUCT_SEARCH and bool(ordered_ids)
        return {
            "reply": (
                catalog_results_response(locale)
                if product_search
                else grounding_fallback_response(locale)
            ),
            "product_ids": ordered_ids[:5] if product_search else [],
            "verdict": "FALLBACK",
            "degraded": True,
            "trusted_reply": product_search,
            "reason_code": f"grounding_{problem}",
            "blocked_canary": canary,
        }

    async def _repair_answer(
        self, messages: Sequence[Any], *, problem: str, locale: Any
    ) -> AnswerDecision | None:
        if self._llm is None:
            return None
        correction = (
            "CORRECAO OBRIGATORIA: a resposta anterior citou "
            + ("ids que nao existem no CONTEXTO. " if problem == "ids" else "")
            + ("valores que nao existem no CONTEXTO. " if problem == "prices" else "")
            + (
                "CA/NR que nao existem no trecho recuperado. "
                if problem == "knowledge_numbers"
                else ""
            )
            + "Responda de novo SOMENTE com o JSON do schema, usando apenas ids do "
            "CONTEXTO e, se houver preco no CONTEXTO, somente esses valores. "
            "Se o preco nao estiver no CONTEXTO, diga que e sob consulta. "
            "Nao escreva valores inventados."
        )
        try:
            return await asyncio.wait_for(
                self._llm.complete_structured(
                    schema=AnswerDecision,
                    messages=[*messages, {"role": "user", "content": correction}],
                    temperature=0.1,
                ),
                timeout=self._regeneration_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - fallback usa template + cartoes
            _log_llm_failure("repair", exc)
            return None

    async def _output_guard(self, state: ChatState) -> dict[str, Any]:
        if state.get("blocked"):
            return {}
        canary = state.get("blocked_canary") or ""
        locale = resolve_locale(state["reply_language"])
        system_prompt = (
            self._system_template.replace("{locale}", state["reply_language"])
            .replace("{language_name}", language_name(locale))
            .replace("{canary}", canary or "-")
        )
        guarded = guard_model_output(
            state.get("reply", ""),
            locale=locale,
            max_chars=ANSWER_MAX_CHARS,
            canary=canary or None,
            system_prompt=system_prompt,
            # Frete e uma regra publica do codigo. Em produto, o preco so
            # existe no CONTEXTO quando o usuario esta logado; a resposta e
            # validada contra os precos do banco abaixo.
            allow_money=state["intent"] == ChatIntent.SHIPPING_POLICY
            or bool(state.get("grounded_context"))
            or bool(state.get("currency_confirmation"))
            or state["intent"] == ChatIntent.PRICE_RANGE,
            # Respostas deterministicas ja sao localizadas pelo codigo; nao
            # passam pelo detector (que confundia PT curto com ES).
            language_detector=None if state.get("trusted_reply") else self._language_detector,
        )
        if (
            not guarded.blocked
            and state.get("grounded_context")
            and not prices_are_grounded(
                guarded.text or "", state.get("allowed_prices", frozenset())
            )
        ):
            metrics.increment_ai_guard_block(agent="chat")
            return {
                "reply": price_unverified_response(resolve_locale(state["reply_language"])),
                "product_ids": state.get("product_ids") or _ordered_ids(state)[:5],
                "verdict": "BLOCK",
                "reason_code": "price_not_grounded",
            }
        if guarded.blocked:
            metrics.increment_ai_guard_block(agent="chat")
            if guarded.reason_code == "idioma_divergente":
                fallback = self._deterministic_answer(state, locale)
                fallback["verdict"] = "BLOCK"
                fallback["reason_code"] = "idioma_divergente"
                return fallback
            return {
                "reply": neutral_response(locale),
                "product_ids": [],
                "verdict": "BLOCK",
                "reason_code": guarded.reason_code or "output_blocked",
            }
        return {"reply": guarded.text or neutral_response(locale)}

    async def _safe_audit(self, **kwargs: Any) -> None:
        """Auditoria nunca derruba a resposta do chat; a causa fica no log."""
        try:
            await self._audit.record(**kwargs)
        except Exception as exc:
            _logger.exception(
                "chat_audit_failed",
                audit_event=str(kwargs.get("event", "")),
                verdict=str(kwargs.get("verdict", "")),
                reason_code=str(kwargs.get("reason_code", "")),
                error_type=type(exc).__name__,
            )

    async def _persist(self, state: ChatState) -> dict[str, Any]:  # noqa: C901 - resiliencia
        conversation = state["conversation"]
        language = state["reply_language"]
        if not state.get("blocked"):
            try:
                await self._conversations.append_user_message(
                    conversation, sanitized_text=state["message"], language=language
                )
            except Exception as exc:  # noqa: BLE001 - resposta nao depende do historico
                _log_llm_failure("persist_user", exc)
        reply = state.get("reply", "")
        try:
            await self._conversations.append_assistant_message(
                conversation, approved_text=reply, language=language
            )
        except Exception as exc:  # noqa: BLE001 - resposta nao depende do historico
            _log_llm_failure("persist_assistant", exc)
        cards: list[ProductCard] = []
        if not state.get("blocked"):
            try:
                cards = await self._cards.build(
                    requested_ids=state.get("product_ids", []),
                    allowed_product_ids=set(state.get("allowed_ids", set())),
                    locale=state["content_locale"],
                    auth=state.get("_auth"),
                )
            except Exception as exc:  # noqa: BLE001 - texto/cards nao podem virar 500
                _log_llm_failure("persist_cards", exc)
        for product_id, reason in state.get("quarantined", []):
            await self._safe_audit(
                company_id=state.get("company_id"),
                event="chat.tool_quarantine",
                verdict="BLOCK",
                reason_code=reason,
                extra={"product_id": product_id},
            )
        decision = state.get("intent_decision")
        if self._session_store is not None and decision is not None and not state.get("blocked"):
            product_ids = tuple(card.product_id for card in cards) or tuple(
                state.get("product_ids", [])
            )
            try:
                await self._session_store.save(
                    conversation.id,
                    session_from_decision(
                        decision,
                        product_ids=product_ids,
                        previous=state.get("session"),
                    ),
                )
            except Exception:  # noqa: BLE001 - sessao nunca derruba a resposta
                _logger.warning("chat_session_save_failed")
        output = state.get("tool_output")
        _logger.info(
            "chat_turn",
            intent=(
                decision.intent.value if decision is not None else state.get("intent", "UNKNOWN")
            ),
            category=decision.category if decision is not None else None,
            brand=decision.brand if decision is not None else None,
            price_sort=(
                decision.price_sort.value
                if decision is not None and decision.price_sort is not None
                else None
            ),
            price_min=decision.price_min if decision is not None else None,
            price_max=decision.price_max if decision is not None else None,
            task=decision.task if decision is not None else None,
            attributes=decision.attributes if decision is not None else {},
            results=len(cards),
            language=language,
            language_detected=state.get("detected_language"),
            detected_confidence=round(float(state.get("detected_confidence", 0.0)), 3),
            regenerated=bool(state.get("regenerated", False)),
            latency_ms=round(
                (time.perf_counter() - state.get("started_at", time.perf_counter())) * 1000,
                1,
            ),
            router_ms=state.get("router_ms"),
            retrieve_ms=state.get("retrieve_ms"),
            answer_ms=state.get("answer_ms"),
            fallback=bool(state.get("degraded", False))
            or state.get("verdict") in ("BLOCK", "FALLBACK"),
            capped=bool(output.price_scan_capped) if output is not None else False,
            reason_code=state.get("reason_code", "chat_turn"),
        )
        await self._safe_audit(
            company_id=state.get("company_id"),
            event="chat.turn",
            verdict=state.get("verdict", "ALLOW"),
            reason_code=state.get("reason_code", "chat_turn"),
            text=state["message"],
        )
        return {
            "outcome": ChatRunResult(
                reply=reply,
                cards=cards,
                verdict=state.get("verdict", "ALLOW"),
                reason_code=state.get("reason_code", "chat_turn"),
                degraded=state.get("degraded", False),
            )
        }

    def _tag(self) -> str:
        return self._tag_factory()


def _log_llm_failure(stage: str, exc: BaseException) -> None:
    """Loga o TIPO real da falha, sem prompt/conteudo/PII."""
    kind = "unexpected"
    if isinstance(exc, LLMQueueFullError):
        kind = "queue_full"
    elif isinstance(exc, TimeoutError):
        kind = "timeout"
    elif isinstance(exc, LLMUnavailableError):
        kind = str(getattr(exc, "kind", "") or "llm_unavailable")
    _logger.warning(
        "llm_call_failed",
        stage=stage,
        kind=kind,
        error_type=type(exc).__name__,
    )


_NEAR_TOKEN = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_NEAR_STOPWORDS = frozenset(
    {
        "para",
        "com",
        "uma",
        "dos",
        "das",
        "por",
        "the",
        "and",
        "for",
        "with",
        "que",
        "voce",
        "você",
        "loja",
        "tem",
        "have",
        "sell",
        "stock",
    }
)


def _near_queries(query: str) -> list[str]:
    """Sinonimos pt/en + token principal, para sugestao quando nao ha exato."""
    pt, en = normalize_query(query)
    tokens = [
        token.casefold()
        for token in _NEAR_TOKEN.findall(query)
        if token.casefold() not in _NEAR_STOPWORDS
    ]
    candidates = [pt, en, tokens[0] if tokens else ""]
    result: list[str] = []
    seen = {query.strip().casefold()}
    for candidate in candidates:
        item = candidate.strip()
        key = item.casefold()
        if len(item) < 2 or key in seen:
            continue
        seen.add(key)
        result.append(item[:200])
    return result[:3]


def _category_names(context_text: str) -> list[str]:
    names = [match.strip() for match in re.findall(r"(?m)^name=(.+)$", context_text)]
    if names:
        return names[:5]
    return [line.strip()[:60] for line in context_text.splitlines() if line.strip()][:5]


def _quarantine(output: ToolOutput) -> list[tuple[str, str]]:
    return [(doc.product_id, doc.reason_code or "quarantine") for doc in output.quarantined]


def _filter_unknown_ids(text: str, allowed: set[str]) -> str:
    """Remove UUIDs que nao vieram das ferramentas deste turno."""

    def _keep(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0).lower() in allowed else ""

    cleaned = _UUID.sub(_keep, text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


_DIRECT_TEXT = {
    ChatIntent.OFF_TOPIC: neutral_response,
    ChatIntent.GREETING: greeting_response,
    ChatIntent.INFO: info_response,
    ChatIntent.LOGIN_REQUIRED: login_required_response,
    ChatIntent.NOT_FOUND: not_found_response,
    ChatIntent.TOOL_ERROR: tool_error_response,
}


def _requested_limit(decision: IntentDecision | None) -> int:
    if decision is None or decision.quantity is None:
        return 5
    return max(1, min(int(decision.quantity), 5))


def _query_for(decision: IntentDecision, message: str) -> str:
    query = (decision.query or message).strip()
    return query if len(query) >= 2 else message.strip()


def _with_grounded(result: dict[str, Any]) -> dict[str, Any]:
    output = result.get("tool_output")
    if isinstance(output, ToolOutput):
        result.setdefault("grounded_context", output.grounded_json())
        result.setdefault("allowed_prices", output.allowed_prices)
    else:
        result.setdefault("grounded_context", "")
        result.setdefault("allowed_prices", frozenset())
    result.setdefault("knowledge_text", "")
    return result


def _base_state(intent: ChatIntent, reason: str) -> dict[str, Any]:
    return {
        "intent": intent,
        "tool_output": None,
        "context_text": "",
        "allowed_ids": set(),
        "quarantined": [],
        "reason_code": reason,
    }


def _login_required_state(reason: str) -> dict[str, Any]:
    return _base_state(ChatIntent.LOGIN_REQUIRED, reason)


def _not_found_state(reason: str) -> dict[str, Any]:
    return _base_state(ChatIntent.NOT_FOUND, reason)


def _clarify_state(reason: str) -> dict[str, Any]:
    return _base_state(ChatIntent.CLARIFY, reason)


def _tool_error_state(reason: str) -> dict[str, Any]:
    return _base_state(ChatIntent.TOOL_ERROR, reason)


def _map_intent(intent: IntentName) -> ChatIntent:  # noqa: C901 - tabela de intencoes
    """Mapeia a intencao da Fase 1 para o no de recuperacao existente."""
    if intent in (
        IntentName.PRODUCT_SEARCH,
        IntentName.PRODUCT_COMPARE,
        IntentName.PRODUCT_DETAIL,
        IntentName.PRICE_QUESTION,
        IntentName.AVAILABILITY,
    ):
        return ChatIntent.PRODUCT_SEARCH
    if intent == IntentName.SHIPPING_QUESTION:
        return ChatIntent.SHIPPING_POLICY
    if intent == IntentName.CART_HELP:
        return ChatIntent.CART_HELP
    if intent == IntentName.ORDER_STATUS:
        return ChatIntent.ORDER_STATUS
    if intent == IntentName.CATALOG_HELP:
        return ChatIntent.CATALOG_HELP
    if intent == IntentName.BRAND_LIST:
        return ChatIntent.BRAND_LIST
    if intent == IntentName.BRAND_PRODUCTS:
        return ChatIntent.BRAND_PRODUCTS
    if intent == IntentName.CATALOG_OVERVIEW:
        return ChatIntent.CATALOG_OVERVIEW
    if intent == IntentName.PRICE_RANGE:
        return ChatIntent.PRICE_RANGE
    if intent == IntentName.COUNT_PRODUCTS:
        return ChatIntent.COUNT_PRODUCTS
    if intent == IntentName.GREETING_SMALLTALK:
        return ChatIntent.GREETING
    if intent == IntentName.POLICY_FAQ:
        return ChatIntent.KNOWLEDGE
    return ChatIntent.OFF_TOPIC


def _ordered_ids(state: ChatState) -> list[str]:
    output = state.get("tool_output")
    return list(output.product_ids) if output is not None else []


def _first_product_name(context_text: str) -> str:
    match = re.search(r"(?m)^name=(.+)$", context_text)
    return match.group(1).strip() if match else ""


def _consultation_query(decision: IntentDecision, query: str) -> str:
    if decision.task is not None:
        return " ".join(task_terms(decision.task))
    return decision.query or query


def _consultation_attempts(
    sections: Sequence[Any], decision: IntentDecision, query: str
) -> list[tuple[str, str | None]]:
    if not sections:
        return [(_consultation_query(decision, query), decision.category)]
    section = sections[0]
    pairs = list(zip(section.search_terms, section.categories, strict=False))
    product = first_product_term(decision.query or query)
    if product is not None:
        pairs.sort(key=lambda pair: pair[0] != product)
    if not pairs:
        return [(_consultation_query(decision, query), decision.category)]
    return pairs[:4]


def _merge_tool_outputs(outputs: Sequence[ToolOutput], *, limit: int = 5) -> ToolOutput:
    grounded: list[Any] = []
    ids: list[str] = []
    quarantined: list[Any] = []
    prices: set[Any] = set()
    texts: list[str] = []
    capped = False
    for output in outputs:
        for product in output.grounded:
            if product.product_id not in {item.product_id for item in grounded}:
                grounded.append(product)
        for product_id in output.product_ids:
            if product_id not in ids:
                ids.append(product_id)
        quarantined.extend(output.quarantined)
        prices.update(output.allowed_prices)
        if output.context_text:
            texts.append(output.context_text)
        capped = capped or output.price_scan_capped
    return ToolOutput(
        context_text="\n".join(texts),
        product_ids=tuple(ids[:limit]),
        quarantined=tuple(quarantined),
        price_scan_capped=capped,
        grounded=tuple(grounded[:limit]),
        allowed_prices=frozenset(prices),
    )


def _answer_context(state: ChatState) -> str:
    knowledge = state.get("knowledge_text") or ""
    grounded = state.get("grounded_context") or ""
    if knowledge and grounded:
        return f"GUIA:\n{knowledge}\n\nPRODUTOS_JSON:\n{grounded}"
    return knowledge or grounded or state.get("context_text", "")


def _grounded_problem(
    answer: AnswerDecision,
    allowed: set[str],
    allowed_prices: frozenset[Any],
    *,
    knowledge_text: str = "",
) -> str | None:
    # Sem produtos nesta rodada (pedido, KB, categoria), nao ha id de produto
    # a validar: pedido_id e outros UUIDs sao dados legitimos do contexto.
    if allowed:
        if any(pid not in allowed for pid in answer.product_ids):
            return "ids"
        cited = {match.group(0).lower() for match in _UUID.finditer(answer.reply)}
        if cited - allowed:
            return "ids"
    if not prices_are_grounded(answer.reply, allowed_prices):
        return "prices"
    if not knowledge_numbers_grounded(answer.reply, knowledge_text):
        return "knowledge_numbers"
    return None


_CA_VALUE = re.compile(r"(?i)\bCA\s*[:#]?\s*(\d{3,})")
_NR_VALUE = re.compile(r"(?i)\bNR\s*[:#]?\s*(\d{1,4}(?:[.,]\d+)?)")


def knowledge_numbers_grounded(reply: str, knowledge_text: str) -> bool:
    """CA/NR citados na resposta precisam existir no trecho recuperado."""
    values = _CA_VALUE.findall(reply) + _NR_VALUE.findall(reply)
    if not values:
        return True
    if not knowledge_text:
        return False
    normalized = unicodedata.normalize("NFKC", knowledge_text)
    return all(value in normalized for value in values)


def _answer_instruction(decision: IntentDecision | None) -> str:
    """Instrucao extra do redator (preco/ordenacao/visitante) em um so lugar."""
    instruction = (
        "Responda so com base no CONTEXTO em JSON, no idioma da mensagem do "
        "usuario, em 1 a 3 frases. NUNCA invente produtos, precos, estoque, prazos ou links; cite "
        "apenas ids do CONTEXTO."
    )
    if decision is not None and (
        decision.intent
        in (
            IntentName.PRICE_QUESTION,
            IntentName.AVAILABILITY,
            IntentName.PRODUCT_COMPARE,
            IntentName.PRODUCT_DETAIL,
        )
        or decision.price_sort is not None
    ):
        instruction += (
            " O CONTEXTO tem o preco aplicavel ao usuario; use SOMENTE esses "
            "valores se responder sobre preco."
        )
    if decision is not None and decision.quantity is not None:
        instruction += (
            f" O usuario pediu {decision.quantity} produto(s); retorne no maximo "
            "essa quantidade e respeite os cartoes."
        )
    if decision is not None and decision.price_sort is not None:
        direction = (
            "menor para o maior" if decision.price_sort == PriceSort.ASC else "maior para o menor"
        )
        instruction += f" A lista do CONTEXTO ja esta ordenada do {direction} preco pelo sistema."
    if decision is not None and (
        decision.task is not None or decision.intent == IntentName.POLICY_FAQ
    ):
        instruction += (
            " Use a orientacao do GUIA como informacao geral (normas nao sao "
            "aconselhamento juridico) e recomende apenas produtos do JSON."
        )
    if decision is not None and decision.intent == IntentName.ORDER_STATUS:
        instruction += (
            " O CONTEXTO tem um pedido do PROPRIO usuario da sessao: responda "
            "apenas status, data e quantidade de itens; nao invente valores."
        )
    return instruction
