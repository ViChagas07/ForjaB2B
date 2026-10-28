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
from app.modules.ai.application.conversation_service import ConversationService
from app.modules.ai.application.ports import ChatTurn, ConversationView, LLMMessage, LLMPort
from app.modules.ai.application.product_cards import ProductCard, ProductCardService
from app.modules.ai.application.security.budget import estimate_tokens
from app.modules.ai.application.security.input_gate import InputGate, InputOutcome
from app.modules.ai.application.security.prompt_builder import (
    PromptBuilder,
    load_system_prompt_template,
    untrusted_block,
)
from app.modules.ai.application.tools import (
    CatalogTools,
    ListCategoriesArgs,
    SearchProductsArgs,
    ShippingPolicyArgs,
    ToolOutput,
)
from app.modules.ai.domain.security.injection import neutral_response
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import resolve_locale

ANSWER_MAX_CHARS = 600
CHAT_HISTORY_MESSAGES = 10


class ChatIntent(StrEnum):
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    SHIPPING_POLICY = "SHIPPING_POLICY"
    CATALOG_HELP = "CATALOG_HELP"
    CART_HELP = "CART_HELP"
    OFF_TOPIC = "OFF_TOPIC"


class RouterDecision(BaseModel):
    """Saida ESTRITA do roteador (invalida = fallback deterministico)."""

    model_config = ConfigDict(extra="forbid", strict=True)
    intent: ChatIntent


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
_CART_TERMS = ("carrinho", "cart", "carrito")
_SHIPPING_TERMS = ("frete", "shipping", "envio", "delivery")
_CATALOG_TERMS = ("categoria", "categories", "categorias", "catalogo", "catalog")


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
    tool_output: NotRequired[ToolOutput | None]
    context_text: NotRequired[str]
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
        state = await self._graph.ainvoke(
            {
                "conversation": conversation,
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
            return {"intent": ChatIntent.OFF_TOPIC, "reason_code": "sensitive_request"}
        intent = await self._ask_route(state)
        return {"intent": intent, "reason_code": intent.value.lower()}

    async def _ask_route(self, state: ChatState) -> ChatIntent:
        fallback = _fallback_intent(state)
        if not self._ai_enabled or self._llm is None:
            return fallback
        messages: list[LLMMessage] = [
            {
                "role": "system",
                "content": (
                    "Classifique a mensagem do usuario em UMA intent: PRODUCT_SEARCH, "
                    "SHIPPING_POLICY, CATALOG_HELP, CART_HELP, OFF_TOPIC."
                ),
            },
            {
                "role": "user",
                "content": untrusted_block("mensagem_do_usuario", state["message"], self._tag()),
            },
        ]
        started = time.perf_counter()
        try:
            decision = await self._llm.complete_structured(schema=RouterDecision, messages=messages)
        except Exception:  # noqa: BLE001 - fallback deterministico
            metrics.observe_llm_call(
                agent="chat",
                duration=time.perf_counter() - started,
                outcome="error",
                estimated_tokens=estimate_tokens(len(state["message"])),
            )
            return fallback
        metrics.observe_llm_call(
            agent="chat",
            duration=time.perf_counter() - started,
            outcome="ok",
            estimated_tokens=estimate_tokens(len(state["message"])),
        )
        return decision.intent

    async def _retrieve(self, state: ChatState) -> dict[str, Any]:
        intent = state["intent"]
        if intent == ChatIntent.OFF_TOPIC:
            return {
                "tool_output": None,
                "context_text": "",
                "allowed_ids": set(),
                "quarantined": [],
            }
        if intent == ChatIntent.CART_HELP:
            company_id, user_id = state.get("company_id"), state.get("user_id")
            if company_id is None or user_id is None or self._cart_summary is None:
                return {
                    "intent": ChatIntent.OFF_TOPIC,
                    "tool_output": None,
                    "context_text": "",
                    "allowed_ids": set(),
                    "quarantined": [],
                    "reason_code": "cart_requires_login",
                }
            summary = await self._cart_summary.cart_summary(company_id=company_id, user_id=user_id)
            return {
                "tool_output": None,
                "context_text": f"carrinho_do_usuario: {summary}",
                "allowed_ids": set(),
                "quarantined": [],
            }
        if intent == ChatIntent.SHIPPING_POLICY:
            output = self._tools.get_shipping_policy(ShippingPolicyArgs(), locale=state["locale"])
            return {
                "tool_output": output,
                "context_text": output.context_text,
                "allowed_ids": set(output.product_ids),
                "quarantined": _quarantine(output),
            }
        if intent == ChatIntent.CATALOG_HELP:
            output = await self._tools.list_categories(ListCategoriesArgs(), locale=state["locale"])
            return {
                "tool_output": output,
                "context_text": output.context_text,
                "allowed_ids": set(output.product_ids),
                "quarantined": _quarantine(output),
            }
        output = await self._tools.search_products(
            SearchProductsArgs.model_validate({"query": state["message"][:200], "limit": 6}),
            locale=state["locale"],
            auth=state.get("_auth"),
        )
        return {
            "tool_output": output,
            "context_text": output.context_text,
            "allowed_ids": set(output.product_ids),
            "quarantined": _quarantine(output),
        }

    async def _answer(self, state: ChatState) -> dict[str, Any]:
        if state.get("blocked"):
            return {}
        if state["intent"] == ChatIntent.OFF_TOPIC:
            return {
                "reply": neutral_response(resolve_locale(state["locale"])),
                "product_ids": [],
            }
        allowed = set(state.get("allowed_ids", set()))
        fallback = neutral_response(resolve_locale(state["locale"]))
        if not self._ai_enabled or self._llm is None:
            # Degradacao: PRODUCT_SEARCH ainda devolve os cartoes da busca.
            return {
                "reply": fallback,
                "product_ids": (
                    sorted(allowed) if state["intent"] == ChatIntent.PRODUCT_SEARCH else []
                ),
                "degraded": True,
            }
        canary = secrets.token_hex(8)
        builder = PromptBuilder(canary_token=canary)
        messages = builder.build(
            locale=resolve_locale(state["locale"]),
            user_message=state["message"],
            history=[(turn.role, turn.content) for turn in state["history"]],
            tool_context=state.get("context_text") or None,
        )
        messages.insert(
            0,
            {
                "role": "system",
                "content": (
                    "Responda so com base no contexto recebido, no idioma do sistema, de "
                    "forma curta. NUNCA invente produtos, precos, prazos ou links; use "
                    "product_ids apenas com identificadores do contexto."
                ),
            },
        )
        started = time.perf_counter()
        try:
            decision = await self._llm.complete_structured(schema=AnswerDecision, messages=messages)
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
                "product_ids": sorted(allowed)
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
        valid_ids = [pid for pid in decision.product_ids if pid in allowed]
        return {"reply": decision.reply, "product_ids": valid_ids, "blocked_canary": canary}

    async def _output_guard(self, state: ChatState) -> dict[str, Any]:
        if state.get("blocked"):
            return {}
        canary = state.get("blocked_canary") or ""
        system_prompt = self._system_template.format(locale=state["locale"], canary=canary or "-")
        guarded = guard_model_output(
            state.get("reply", ""),
            locale=resolve_locale(state["locale"]),
            max_chars=ANSWER_MAX_CHARS,
            canary=canary or None,
            system_prompt=system_prompt,
        )
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


def _fallback_intent(state: ChatState) -> ChatIntent:
    lowered = state["message"].lower()
    if any(term in lowered for term in _SENSITIVE_TERMS):
        return ChatIntent.OFF_TOPIC
    if any(term in lowered for term in _SHIPPING_TERMS):
        return ChatIntent.SHIPPING_POLICY
    if any(term in lowered for term in _CART_TERMS):
        return ChatIntent.CART_HELP if state.get("company_id") else ChatIntent.OFF_TOPIC
    if any(term in lowered for term in _CATALOG_TERMS):
        return ChatIntent.CATALOG_HELP
    return ChatIntent.PRODUCT_SEARCH
