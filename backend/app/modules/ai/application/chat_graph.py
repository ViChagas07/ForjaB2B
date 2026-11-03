"""Grafo do assistente de chat (FASE 5c) — topologia FIXA, sem loop livre.

input_guard -> route -> retrieve -> answer -> output_guard -> persist -> end.

- input_guard: gate da Fase 2 (toda mensagem + janela; 3 bloqueios = CLOSE).
- route: LLM estruturado (intent) com fallback deterministico; pedidos
  sensiveis (dados de outra empresa, desconto, alterar preco, instrucoes do
  sistema) ja caem em OFF_TOPIC/resposta neutra ANTES do LLM.
- retrieve: codigo, por intent, usando as FERRAMENTAS da Fase 5b (somente
  leitura; saida ja sanitizada/quarentenada; nunca preco). CART_HELP so para
  logado e so resumo do proprio carrinho, sem precos.
- answer: LLM curto no locale, so com o contexto; devolve product_ids que sao
  FILTRADOS para o conjunto devolvido pelas ferramentas NESTE turno.
- output_guard: guard da Fase 2 (URLs/PII/segredos/precos/idioma/canary).
- persist: conversation_service (user sanitizado + assistant aprovado), audit
  sem PII e cartoes montados pelo backend.

Kill switch ou falha de LLM: resposta neutra traduzida; em PRODUCT_SEARCH os
cartoes da busca deterministica continuam (degradacao graciosa). Nenhum custo
de LLM quando AI_AGENTS_ENABLED=false.
"""

from __future__ import annotations

import re
import secrets
import time
import uuid
from collections.abc import Callable, Sequence
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
from app.modules.ai.application.ports import ChatTurn, ConversationView, LLMPort
from app.modules.ai.application.product_cards import ProductCard, ProductCardService
from app.modules.ai.application.security.budget import estimate_tokens
from app.modules.ai.application.security.input_gate import InputGate, InputOutcome
from app.modules.ai.application.security.prompt_builder import (
    PromptBuilder,
    load_system_prompt_template,
)
from app.modules.ai.application.tools import (
    CatalogTools,
    CompareProductsArgs,
    GetProductArgs,
    ListCategoriesArgs,
    OrderStatusArgs,
    SearchProductsArgs,
    ShippingPolicyArgs,
    ToolOutput,
)
from app.modules.ai.domain.degradation import (
    clarify_response,
    demo_mode_response,
    greeting_response,
    grounding_fallback_response,
    info_response,
    login_required_response,
    not_found_response,
    price_question_response,
    price_sort_response,
    price_unverified_response,
    tool_error_response,
)
from app.modules.ai.domain.security.catalog_sanitizer import sanitize_tool_text
from app.modules.ai.domain.security.grounding import prices_are_grounded
from app.modules.ai.domain.security.injection import neutral_response
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import resolve_locale

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


_SENSITIVE_TERMS = (
    "outra empresa",
    "otra empresa",
    "other company",
    "desconto",
    "discount",
    "descuento",
    "alterar o preco",
    "change the price",
    "cambiar el precio",
    "preco especial",
    "precio especial",
    "preco negociado",
    "precio negociado",
    "contrato",
    "cnpj",
)


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
    locale: str
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
        self._system_template = load_system_prompt_template()
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
        locale: str,
        message: str,
        history: Sequence[ChatTurn],
        auth: Any,
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
                "locale": locale,
                "message": message,
                "history": list(history),
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
            locale=resolve_locale(state["locale"]),
            raw_message=state["message"],
            recent_user_messages=[turn.content for turn in state["history"] if turn.role == "user"],
        )
        if decision.outcome in (InputOutcome.BLOCK, InputOutcome.CLOSE):
            metrics.increment_ai_guard_block(agent="chat")
            return {
                "blocked": True,
                "verdict": "BLOCK",
                "reason_code": decision.reason_code or "input_blocked",
                "reply": neutral_response(resolve_locale(state["locale"])),
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
                    intent=IntentName.OUT_OF_SCOPE, language=state["locale"]
                ),
                "reason_code": "sensitive_request",
            }
        session = state.get("session")
        follow_up = (
            follow_up_decision(session, state["message"], locale=state["locale"])
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
        decision = deterministic_decision(state["message"], locale=state["locale"])
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
            decision = fallback_decision(state["message"], locale=state["locale"])
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
            locale=state["locale"],
            tag=self._tag(),
        )
        started = time.perf_counter()
        try:
            decision = await self._llm.complete_structured(
                schema=IntentDecision,
                messages=messages,
                temperature=0.1,
            )
        except Exception:  # noqa: BLE001 - fallback deterministico
            metrics.observe_llm_call(
                agent="chat",
                duration=time.perf_counter() - started,
                outcome="error",
                estimated_tokens=estimate_tokens(len(state["message"])),
            )
            return None
        metrics.observe_llm_call(
            agent="chat",
            duration=time.perf_counter() - started,
            outcome="ok",
            estimated_tokens=estimate_tokens(len(state["message"])),
        )
        return normalize_decision(decision, message=state["message"], locale=state["locale"])

    async def _retrieve(self, state: ChatState) -> dict[str, Any]:
        """Executa ferramentas; qualquer falha vira mensagem amigavel (sem 500)."""
        try:
            result = await self._retrieve_inner(state)
            return _with_grounded(result)
        except Exception:
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

    async def _retrieve_inner(self, state: ChatState) -> dict[str, Any]:
        intent = state["intent"]
        auth = state.get("_auth")
        special = self._special_retrieve(state)
        if special is not None:
            return special
        decision = state.get("intent_decision") or fallback_decision(
            state["message"], locale=state["locale"]
        )
        query = _query_for(decision, state["message"])
        if intent == ChatIntent.ORDER_STATUS:
            return await self._order_retrieve(state, decision, auth)
        if intent == ChatIntent.CART_HELP:
            return await self._cart_retrieve(state)
        if intent == ChatIntent.SHIPPING_POLICY:
            return self._shipping_retrieve(state)
        if intent == ChatIntent.CATALOG_HELP:
            return await self._catalog_retrieve(state)
        return await self._product_dispatch(decision, query=query, state=state, auth=auth)

    async def _search_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState, auth: Any
    ) -> dict[str, Any]:
        limit = _requested_limit(decision)
        args: dict[str, Any] = {
            "query": query[:200],
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
        output = await self._tools.search_products(search_args, locale=state["locale"], auth=auth)
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    def _shipping_retrieve(self, state: ChatState) -> dict[str, Any]:
        output = self._tools.get_shipping_policy(ShippingPolicyArgs(), locale=state["locale"])
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    async def _catalog_retrieve(self, state: ChatState) -> dict[str, Any]:
        output = await self._tools.list_categories(ListCategoriesArgs(), locale=state["locale"])
        return {
            "tool_output": output,
            "context_text": output.context_text[:MAX_CONTEXT_CHARS],
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
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
        sections = self._knowledge.search(state["message"], limit=2)
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
            self._knowledge.search(decision.task or query, limit=2)
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
            search_args, locale=state["locale"], auth=state.get("_auth")
        )

    async def _compare_retrieve(
        self, decision: IntentDecision, *, query: str, state: ChatState
    ) -> dict[str, Any]:
        refs = list(decision.product_refs)
        if len(refs) < 2:
            nearest = await self._tools.search_products(
                SearchProductsArgs.model_validate({"query": query[:200], "limit": 2}),
                locale=state["locale"],
                auth=state.get("_auth"),
            )
            refs = list(nearest.product_ids)
        if len(refs) < 2:
            return _clarify_state("compare_needs_two")
        output = await self._tools.compare_products(
            CompareProductsArgs(product_refs=refs[:4]),
            locale=state["locale"],
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
                SearchProductsArgs.model_validate({"query": query[:200], "limit": 1}),
                locale=state["locale"],
                auth=state.get("_auth"),
            )
            ref = nearest.product_ids[0] if nearest.product_ids else None
        if ref is None:
            return _clarify_state("product_not_provided")
        output = await self._tools.get_product(
            GetProductArgs(product_ref=ref),
            locale=state["locale"],
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

    def _direct_answer(self, state: ChatState, locale: Any) -> dict[str, Any] | None:
        """Respostas de codigo (sem LLM): estado, saudacao, frete e preco."""
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
        if decision.price_sort == PriceSort.ASC:
            output = state.get("tool_output")
            capped = bool(output.price_scan_capped) if output is not None else False
            return {
                "reply": price_sort_response(locale, name=name, visitor=False, capped=capped),
                "product_ids": ordered_ids[:5],
            }
        return None

    async def _answer(self, state: ChatState) -> dict[str, Any]:
        if state.get("blocked"):
            return {}
        locale = resolve_locale(state["locale"])
        direct = self._direct_answer(state, locale)
        if direct is not None:
            return direct
        allowed = set(state.get("allowed_ids", set()))
        ordered_ids = _ordered_ids(state)
        decision = state.get("intent_decision")
        fallback = demo_mode_response(locale)
        if not self._ai_enabled or self._llm is None:
            # Degradacao: PRODUCT_SEARCH ainda devolve os cartoes da busca.
            return {
                "reply": fallback,
                "product_ids": (
                    ordered_ids[:5] if state["intent"] == ChatIntent.PRODUCT_SEARCH else []
                ),
                "degraded": True,
            }
        canary = secrets.token_hex(8)
        builder = PromptBuilder(canary_token=canary)
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
        started = time.perf_counter()
        try:
            answer = await self._llm.complete_structured(schema=AnswerDecision, messages=messages)
        except Exception:  # noqa: BLE001 - degrada com cartoes deterministicos
            metrics.observe_llm_call(
                agent="chat",
                duration=time.perf_counter() - started,
                outcome="error",
                estimated_tokens=estimate_tokens(
                    len(state["message"]) + len(state.get("context_text", ""))
                ),
            )
            return {
                "reply": fallback,
                "product_ids": ordered_ids[:5]
                if state["intent"] == ChatIntent.PRODUCT_SEARCH
                else [],
                "degraded": True,
            }
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
            allowed_prices=frozenset(state.get("allowed_prices", frozenset())),
            state=state,
            ordered_ids=ordered_ids,
            canary=canary,
            locale=locale,
        )
        if isinstance(repaired, dict):
            return repaired
        answer = repaired
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
            reply = fallback
            return {
                "reply": reply,
                "product_ids": (
                    ordered_ids[:5] if state["intent"] == ChatIntent.PRODUCT_SEARCH else []
                ),
                "degraded": True,
                "blocked_canary": canary,
            }
        return {"reply": reply, "product_ids": valid_ids, "blocked_canary": canary}

    async def _maybe_repair(
        self,
        answer: AnswerDecision,
        messages: Sequence[Any],
        *,
        allowed: set[str],
        allowed_prices: frozenset[Any],
        state: ChatState,
        ordered_ids: list[str],
        canary: str,
        locale: Any,
    ) -> AnswerDecision | dict[str, Any]:
        problem = _grounded_problem(answer, allowed, allowed_prices)
        if problem is None:
            return answer
        repaired = await self._repair_answer(messages, problem=problem, locale=locale)
        if repaired is not None and _grounded_problem(repaired, allowed, allowed_prices) is None:
            return repaired
        _logger.warning(
            "chat_grounding_fallback",
            problem=problem,
            intent=state.get("intent", "UNKNOWN"),
        )
        return {
            "reply": grounding_fallback_response(locale),
            "product_ids": (
                ordered_ids[:5] if state["intent"] == ChatIntent.PRODUCT_SEARCH else []
            ),
            "verdict": "FALLBACK",
            "degraded": True,
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
            + "Responda de novo SOMENTE com o JSON do schema, usando apenas ids do "
            "CONTEXTO e, se houver preco no CONTEXTO, somente esses valores. "
            "Se o preco nao estiver no CONTEXTO, diga que e sob consulta. "
            "Nao escreva valores inventados."
        )
        try:
            return await self._llm.complete_structured(
                schema=AnswerDecision,
                messages=[*messages, {"role": "user", "content": correction}],
                temperature=0.1,
            )
        except Exception:  # noqa: BLE001 - fallback usa template + cartoes
            return None

    async def _output_guard(self, state: ChatState) -> dict[str, Any]:
        if state.get("blocked"):
            return {}
        canary = state.get("blocked_canary") or ""
        system_prompt = self._system_template.replace("{locale}", state["locale"]).replace(
            "{canary}", canary or "-"
        )
        guarded = guard_model_output(
            state.get("reply", ""),
            locale=resolve_locale(state["locale"]),
            max_chars=ANSWER_MAX_CHARS,
            canary=canary or None,
            system_prompt=system_prompt,
            # Frete e uma regra publica do codigo. Em produto, o preco so
            # existe no CONTEXTO quando o usuario esta logado; a resposta e
            # validada contra os precos do banco abaixo.
            allow_money=state["intent"] == ChatIntent.SHIPPING_POLICY
            or bool(state.get("grounded_context")),
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
                "reply": price_unverified_response(resolve_locale(state["locale"])),
                "product_ids": state.get("product_ids") or _ordered_ids(state)[:5],
                "verdict": "BLOCK",
                "reason_code": "price_not_grounded",
            }
        if guarded.blocked:
            metrics.increment_ai_guard_block(agent="chat")
            return {
                "reply": neutral_response(resolve_locale(state["locale"])),
                "product_ids": [],
                "verdict": "BLOCK",
                "reason_code": guarded.reason_code or "output_blocked",
            }
        return {"reply": guarded.text or neutral_response(resolve_locale(state["locale"]))}

    async def _persist(self, state: ChatState) -> dict[str, Any]:
        conversation = state["conversation"]
        if not state.get("blocked"):
            await self._conversations.append_user_message(
                conversation, sanitized_text=state["message"]
            )
        reply = state.get("reply", "")
        await self._conversations.append_assistant_message(conversation, approved_text=reply)
        cards: list[ProductCard] = []
        if not state.get("blocked"):
            cards = await self._cards.build(
                requested_ids=state.get("product_ids", []),
                allowed_product_ids=set(state.get("allowed_ids", set())),
                locale=state["locale"],
                auth=state.get("_auth"),
            )
        for product_id, reason in state.get("quarantined", []):
            await self._audit.record(
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
                    session_from_decision(decision, product_ids=product_ids),
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
            fallback=bool(state.get("degraded", False))
            or state.get("verdict") in ("BLOCK", "FALLBACK"),
            capped=bool(output.price_scan_capped) if output is not None else False,
            reason_code=state.get("reason_code", "chat_turn"),
        )
        await self._audit.record(
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


def _map_intent(intent: IntentName) -> ChatIntent:
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


def _consultation_attempts(
    sections: Sequence[Any], decision: IntentDecision, query: str
) -> list[tuple[str, str | None]]:
    if not sections:
        return [(decision.query or decision.task or query, decision.category)]
    section = sections[0]
    pairs = list(zip(section.search_terms, section.categories, strict=False))
    product = first_product_term(decision.query or query)
    if product is not None:
        pairs.sort(key=lambda pair: pair[0] != product)
    if not pairs:
        return [(decision.query or decision.task or query, decision.category)]
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
    answer: AnswerDecision, allowed: set[str], allowed_prices: frozenset[Any]
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
    return None


def _answer_instruction(decision: IntentDecision | None) -> str:
    """Instrucao extra do redator (preco/ordenacao/visitante) em um so lugar."""
    instruction = (
        "Responda so com base no CONTEXTO em JSON, no idioma do sistema, em 1 a 3 "
        "frases. NUNCA invente produtos, precos, estoque, prazos ou links; cite "
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
