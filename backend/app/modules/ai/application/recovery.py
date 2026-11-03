"""Grafo do agente de recuperacao de carrinho (application, LangGraph).

Topologia FIXA (sem loop livre de ferramentas):
load_context -> policy -> decide -> validate -> act -> end.

- load_context: codigo (o snapshot vem do job com contexto RLS; identidade
  NUNCA vem do LLM).
- policy: codigo (`evaluate_recovery`) — elegibilidade + acoes permitidas +
  reason_hints. Inelegivel => grafo TERMINA sem LLM nem envio.
- decide: acao/reason escolhidos EXCLUSIVAMENTE pelo codigo
  (`select_recovery_action`). O LLM recebe os fatos prontos (empresa, itens,
  subtotal, frete, desconto ja calculado, link) e escreve APENAS o paragrafo
  persuasivo no locale do cliente. Kill switch/falha => texto vazio e
  template fixo (o e-mail sempre sai).
- validate: guard de saida (HTML/URL/PII/idioma/injecao) + validacao
  numerica: nenhum percentual/valor diferente do calculado pode passar.
- act: codigo — cria oferta (se FREE_SHIPPING/DISCOUNT_3PCT), enfileira
  cart.recovery no outbox, grava attempt + audit (uma transacao).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, NotRequired, Protocol, TypedDict

from langgraph.graph import END, StateGraph

from app.modules.ai.application.ports import LLMMessage, LLMPort
from app.modules.ai.application.security.prompt_builder import untrusted_block
from app.modules.ai.domain.recovery import (
    CartSnapshot,
    RecoveryAction,
    RecoveryConfig,
    RecoveryFacts,
    RecoveryPolicy,
    RecoveryReason,
    build_recovery_facts,
    evaluate_recovery,
    select_recovery_action,
)
from app.modules.ai.domain.recovery_copy import validate_recovery_copy
from app.modules.ai.domain.security.injection import scan_injection
from app.modules.ai.domain.security.output_guard import guard_model_output
from app.modules.ai.domain.types import resolve_locale

NOTE_MAX_CHARS = 600

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
    company_name: str
    items_summary: str
    cart_url: str
    policy: NotRequired[RecoveryPolicy]
    action: NotRequired[RecoveryAction]
    reason_code: NotRequired[RecoveryReason]
    facts: NotRequired[RecoveryFacts]
    copy: NotRequired[str]
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
        company_name: str,
        items_summary: str,
        cart_url: str,
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
                "company_name": company_name,
                "items_summary": items_summary,
                "cart_url": cart_url,
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
        action, reason = select_recovery_action(state["snapshot"], policy, config=self._config)
        facts = build_recovery_facts(
            state["snapshot"],
            action=action,
            company_name=state["company_name"],
            items_summary=state["items_summary"],
            locale=state["locale"],
            cart_url=state["cart_url"],
            config=self._config,
        )
        copy, degraded = await self._write_copy(facts)
        return {
            "action": action,
            "reason_code": reason,
            "facts": facts,
            "copy": copy,
            "degraded": degraded,
        }

    async def _write_copy(self, facts: RecoveryFacts) -> tuple[str, bool]:
        """Texto persuasivo do LLM; vazio + template fixo em qualquer falha."""
        if not self._ai_enabled or self._llm is None:
            return "", True
        tag = self._tag_factory()
        data = _facts_block(facts)
        messages: list[LLMMessage] = [
            {
                "role": "system",
                "content": (
                    "Voce escreve SOMENTE o paragrafo persuasivo de um e-mail de "
                    "recuperacao de carrinho B2B. Use apenas os fatos fornecidos. "
                    "Nao escreva links, e-mails, telefones, HTML, Markdown, emojis, "
                    "percentuais ou valores diferentes dos informados. Nao prometa "
                    "beneficio que nao esteja em acao. Responda no idioma indicado, "
                    "em texto simples, com no maximo duas frases curtas."
                ),
            },
            {
                "role": "user",
                "content": f"idioma={facts.locale}\n"
                + untrusted_block("fatos_do_carrinho", data, tag),
            },
        ]
        try:
            text = await self._llm.complete_text(messages=messages)
        except Exception:  # noqa: BLE001 - LLM nunca derruba o agente
            return "", True
        text = text.strip()
        if not text:
            return "", True
        locale = resolve_locale(facts.locale)
        guarded = guard_model_output(
            text,
            locale=locale,
            max_chars=NOTE_MAX_CHARS,
            allow_money=True,
        )
        if guarded.blocked or not guarded.text:
            return "", True
        if scan_injection(guarded.text).level.value == "BLOCK":
            return "", True
        validation = validate_recovery_copy(guarded.text, facts=facts, max_chars=NOTE_MAX_CHARS)
        if not validation.ok:
            return "", True
        return guarded.text, False

    async def _validate(self, state: RecoveryState) -> dict[str, Any]:
        copy = state.get("copy", "")
        verdict = "ALLOW"
        degraded = state.get("degraded", False)
        if copy:
            injection = scan_injection(copy)
            if injection.level.value == "BLOCK":
                copy, verdict, degraded = "", "BLOCK", True
        return {"copy": copy, "verdict": verdict, "degraded": degraded}

    async def _act(self, state: RecoveryState) -> dict[str, Any]:
        action = state["action"]
        reason = state["reason_code"]
        persist = state.get("persist")
        if persist is None:  # pragma: no cover - sempre injetado pelo job
            raise RuntimeError("persist nao injetado")
        request = persist(action, reason, state.get("copy", ""), state.get("verdict", "ALLOW"))
        offer_id = await self._persist_port.persist(request)
        return {
            "outcome": RecoveryOutcome(
                action=action,
                reason_code=reason,
                note=state.get("copy", ""),
                offer_id=offer_id,
                degraded=state.get("degraded", False),
                guard_verdict=state.get("verdict", "ALLOW"),
            )
        }


def _facts_block(facts: RecoveryFacts) -> str:
    lines = [
        f"empresa={facts.company_name}",
        f"itens={facts.items_summary}",
        f"subtotal_brl={facts.subtotal:.2f}",
        f"frete_brl={facts.shipping_total:.2f}",
        f"frete_gratis={'true' if facts.action == RecoveryAction.FREE_SHIPPING else 'false'}",
        f"valor_minimo_frete_gratis_brl={facts.free_shipping_min:.2f}",
        f"link_do_carrinho={facts.cart_url} (nao reproduza o link no texto)",
    ]
    if facts.discount_percent is not None:
        lines.append(f"desconto_percentual={facts.discount_percent:.2f}")
    if facts.discount_amount is not None:
        lines.append(f"desconto_brl={facts.discount_amount:.2f}")
    lines.append(f"acao={facts.action.value}")
    return "\n".join(lines)


def offer_text_for(action: RecoveryAction, locale: str) -> str:
    """Slot {offer_text} localizado (backend; nunca do LLM)."""
    table = _OFFER_TEXT.get(action)
    if table is None:
        return ""
    return table.get(locale, table["pt-BR"])
