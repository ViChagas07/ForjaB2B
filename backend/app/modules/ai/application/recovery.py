"""Grafo do agente de recuperacao de carrinho (application, LangGraph).

Topologia FIXA (sem loop livre de ferramentas):
load_context -> policy -> decide -> validate -> act -> end.

- load_context: codigo (o snapshot vem do job com contexto RLS; identidade
  NUNCA vem do LLM).
- policy: codigo (`evaluate_recovery`) — elegibilidade + eligible_actions +
  reason_hints. Inelegivel => grafo TERMINA sem LLM nem envio.
- decide: LLM com saida estruturada ESTRITA (RecoveryDecision): reason_code de
  um enum, chosen_action DENTRO de eligible_actions, personal_note <= 200 no
  locale do usuario. Recebe apenas dados minimos e sem PII/precos brutos
  (contagens e faixas) em bloco nao confiavel da Fase 2. Kill switch off ou
  falha de LLM => REMIND deterministico sem nota (degrada, nunca quebra).
- validate: codigo — acao fora da lista ou nota reprovada pelo guard => REMIND
  sem nota (fallback deterministico).
- act: codigo — cria oferta (se FREE_SHIPPING/DISCOUNT_3PCT), enfileira
  cart.recovery no outbox, grava attempt + audit (uma transacao).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, NotRequired, Protocol, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.application.ports import LLMMessage, LLMPort
from app.modules.ai.application.security.prompt_builder import untrusted_block
from app.modules.ai.domain.recovery import (
    CartSnapshot,
    RecoveryAction,
    RecoveryConfig,
    RecoveryPolicy,
    RecoveryReason,
    evaluate_recovery,
)
from app.modules.ai.domain.security.injection import scan_injection
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import resolve_locale

NOTE_MAX_CHARS = 200

_OFFER_TEXT = {
    RecoveryAction.FREE_SHIPPING: {
        "pt-BR": "O frete deste pedido sai por nossa conta.",
        "en": "Shipping for this order is on us.",
        "es": "El envío de este pedido corre por nuestra cuenta.",
        "ar": "الشحن لهذا الطلب علينا.",
        "de": "Der Versand für diese Bestellung geht auf uns.",
        "fr": "La livraison de cette commande est offerte.",
        "it": "La spedizione di questo ordine è a nostro carico.",
        "ja": "このご注文の送料は無料です。",
        "ko": "이 주문의 배송비는 무료입니다.",
        "ru": "Доставка этого заказа за наш счёт.",
        "zh-CN": "本订单免运费。",
    },
    RecoveryAction.DISCOUNT_3PCT: {
        "pt-BR": "3% de desconto nos itens sem preço negociado deste carrinho.",
        "en": "3% off items without a negotiated price in this cart.",
        "es": "3% de descuento en los artículos sin precio negociado de este carrito.",
        "ar": "خصم 3% على العناصر دون سعر متفاوض عليه في هذه السلة.",
        "de": "3 % Rabatt auf Artikel ohne ausgehandelten Preis in diesem Warenkorb.",
        "fr": "3 % de remise sur les articles sans prix négocié de ce panier.",
        "it": "3% di sconto sugli articoli senza prezzo negoziato di questo carrello.",
        "ja": "このカートの交渉価格以外の商品が3%割引になります。",
        "ko": "이 장바구니의 협상 가격이 아닌 상품에 3% 할인.",
        "ru": "Скидка 3% на товары без договорной цены в этой корзине.",
        "zh-CN": "本购物车中非议价商品享 3% 折扣。",
    },
}


class RecoveryDecision(BaseModel):
    """Saida ESTRITA esperada do LLM (invalida = fallback REMIND sem nota)."""

    model_config = ConfigDict(extra="forbid", strict=True)
    reason_code: RecoveryReason
    chosen_action: RecoveryAction
    personal_note: str = Field(default="", max_length=NOTE_MAX_CHARS)


@dataclass(frozen=True, kw_only=True)
class RecoveryPersistRequest:
    """Dados que o no `act` grava (codigo; nunca decide nada)."""

    cart_id: Any
    company_id: Any
    user_id: Any
    locale: str
    company_name: str
    items_summary: str
    action: RecoveryAction
    reason_code: RecoveryReason
    note: str
    offer_text: str
    guard_verdict: str


@dataclass(frozen=True, kw_only=True)
class RecoveryOutcome:
    action: RecoveryAction
    reason_code: RecoveryReason
    note: str = ""
    offer_id: Any = None
    degraded: bool = False
    guard_verdict: str = "ALLOW"
    attempts: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class RecoveryPersistPort(Protocol):
    """Persistencia do `act` (infrastructure; UMA transacao)."""

    async def persist(self, request: RecoveryPersistRequest) -> Any:
        """Cria oferta (se houver), enfileira cart.recovery e grava attempt/audit."""
        ...


class RecoveryState(TypedDict):
    snapshot: CartSnapshot
    locale: str
    policy: NotRequired[RecoveryPolicy]
    decision: NotRequired[RecoveryDecision]
    outcome: NotRequired[RecoveryOutcome]
    degraded: NotRequired[bool]
    verdict: NotRequired[str]
    last_attempt_at: NotRequired[datetime | None]
    attempts_for_state: NotRequired[int]
    persist: NotRequired[
        Callable[[RecoveryAction, RecoveryReason, str, str], RecoveryPersistRequest]
    ]


class CartRecoveryGraph:
    """Grafo fixo; deps injetadas (LLM/fake, persistencia, config)."""

    def __init__(
        self,
        *,
        llm: LLMPort | None,
        persist_port: RecoveryPersistPort,
        config: RecoveryConfig,
        ai_enabled: bool,
        tag_factory: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._llm = llm
        self._persist_port = persist_port
        self._config = config
        self._ai_enabled = ai_enabled
        self._tag_factory = tag_factory or (lambda: secrets.token_hex(8))
        self._now = now or (lambda: datetime.now(UTC))
        self._graph = self._build()

    def _build(self) -> Any:
        graph: StateGraph[RecoveryState] = StateGraph(RecoveryState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("policy", self._policy)
        graph.add_node("decide", self._decide)
        graph.add_node("validate", self._validate)
        graph.add_node("act", self._act)
        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "policy")
        graph.add_conditional_edges("policy", self._after_policy, {"decide": "decide", "end": END})
        graph.add_edge("decide", "validate")
        graph.add_edge("validate", "act")
        graph.add_edge("act", END)
        return graph.compile()

    async def run(
        self,
        *,
        snapshot: CartSnapshot,
        locale: str,
        last_attempt_at: datetime | None,
        attempts_for_state: int,
        persist_request: Callable[
            [RecoveryAction, RecoveryReason, str, str], RecoveryPersistRequest
        ],
    ) -> RecoveryOutcome | None:
        """Executa o grafo; None = inelegivel (nada e enviado)."""
        state = await self._graph.ainvoke(
            {
                "snapshot": snapshot,
                "locale": locale,
                "last_attempt_at": last_attempt_at,
                "attempts_for_state": attempts_for_state,
                "persist": persist_request,
            }
        )
        outcome = state.get("outcome")
        return outcome if isinstance(outcome, RecoveryOutcome) else None

    # ------------------------------------------------------------------ nodes
    async def _load_context(self, state: RecoveryState) -> dict[str, Any]:
        return {}  # snapshot veio do servidor (job/RLS); nada do LLM

    async def _policy(self, state: RecoveryState) -> dict[str, Any]:
        return {
            "policy": evaluate_recovery(
                state["snapshot"],
                config=self._config,
                now=self._now(),
                last_attempt_at=state.get("last_attempt_at"),
                attempts_for_state=state.get("attempts_for_state", 0),
            )
        }

    def _after_policy(self, state: RecoveryState) -> str:
        policy = state.get("policy")
        return "decide" if policy is not None and policy.eligible else "end"

    async def _decide(self, state: RecoveryState) -> dict[str, Any]:
        policy = state["policy"]
        decision, degraded = await self._ask_llm(state["snapshot"], policy, state["locale"])
        return {"decision": decision, "degraded": degraded}

    async def _ask_llm(
        self, snapshot: CartSnapshot, policy: RecoveryPolicy, locale: str
    ) -> tuple[RecoveryDecision, bool]:
        fallback = RecoveryDecision(
            reason_code=RecoveryReason.CART_IDLE,
            chosen_action=RecoveryAction.REMIND,
            personal_note="",
        )
        if not self._ai_enabled or self._llm is None:
            return fallback, True
        tag = self._tag_factory()
        data = (
            f"itens={snapshot.item_count}; "
            f"faixa_subtotal={_subtotal_band(snapshot.subtotal)}; "
            f"faixa_pedidos_pagos={_orders_band(snapshot.company_paid_orders)}; "
            f"sinais={','.join(h.value for h in policy.reason_hints)}; "
            f"acoes_permitidas={','.join(a.value for a in policy.eligible_actions)}"
        )
        messages: list[LLMMessage] = [
            {
                "role": "system",
                "content": (
                    "Voce escolhe UMA acao permitida e um motivo de um enum para um e-mail "
                    "de recuperacao de carrinho. Nunca invente acoes, precos ou links. "
                    "personal_note: texto curto no idioma pedido, sem dados pessoais."
                ),
            },
            {
                "role": "user",
                "content": f"idioma={locale}\n" + untrusted_block("dados_do_carrinho", data, tag),
            },
        ]
        try:
            decision = await self._llm.complete_structured(
                schema=RecoveryDecision, messages=messages
            )
        except Exception:  # noqa: BLE001 - LLM nunca derruba o agente
            return fallback, True
        if decision.chosen_action not in policy.eligible_actions:
            return fallback, True
        return decision, False

    async def _validate(self, state: RecoveryState) -> dict[str, Any]:
        policy = state["policy"]
        decision = state["decision"]
        degraded = state.get("degraded", False)
        action, reason, note = (
            decision.chosen_action,
            decision.reason_code,
            decision.personal_note.strip(),
        )
        verdict = "ALLOW"
        if action not in policy.eligible_actions:
            action, reason, note, verdict = (
                RecoveryAction.REMIND,
                RecoveryReason.CART_IDLE,
                "",
                "BLOCK",
            )
            degraded = True
        if note:
            locale = resolve_locale(state["locale"])
            guarded = guard_model_output(note, locale=locale, max_chars=NOTE_MAX_CHARS)
            injection = scan_injection(guarded.text) if guarded.text else None
            if (
                guarded.blocked
                or not guarded.text
                or (injection is not None and injection.level.value == "BLOCK")
            ):
                note, verdict = "", "BLOCK"
        return {
            "decision": RecoveryDecision(
                reason_code=reason, chosen_action=action, personal_note=note
            ),
            "verdict": verdict,
            "degraded": degraded,
        }

    async def _act(self, state: RecoveryState) -> dict[str, Any]:
        decision = state["decision"]
        persist = state.get("persist")
        if persist is None:  # pragma: no cover - sempre injetado pelo job
            raise RuntimeError("persist nao injetado")
        request = persist(
            decision.chosen_action,
            decision.reason_code,
            decision.personal_note,
            state.get("verdict", "ALLOW"),
        )
        offer_id = await self._persist_port.persist(request)
        return {
            "outcome": RecoveryOutcome(
                action=decision.chosen_action,
                reason_code=decision.reason_code,
                note=decision.personal_note,
                offer_id=offer_id,
                degraded=state.get("degraded", False),
                guard_verdict=state.get("verdict", "ALLOW"),
            )
        }


def offer_text_for(action: RecoveryAction, locale: str) -> str:
    """Slot {offer_text} localizado (backend; nunca do LLM)."""
    table = _OFFER_TEXT.get(action)
    if table is None:
        return ""
    return table.get(locale, table["pt-BR"])


def _subtotal_band(subtotal: Decimal) -> str:
    if subtotal < Decimal("1500"):
        return "ate_1500"
    if subtotal < Decimal("5000"):
        return "1500_5000"
    if subtotal < Decimal("20000"):
        return "5000_20000"
    return "acima_20000"


def _orders_band(paid_orders: int) -> str:
    if paid_orders <= 0:
        return "nenhum"
    if paid_orders <= 4:
        return "1_4"
    return "5_mais"
