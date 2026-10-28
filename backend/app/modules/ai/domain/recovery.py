"""Politica do agente de recuperacao de carrinho (dominio PURO, sem LLM).

SOMENTE estas regras, sem excecao:
- Elegivel: usuario autenticado, carrinho nao vazio, `last_activity_at` entre
  24h e 7 dias atras, sem pedido da empresa/usuario depois disso, sem opt-out.
- Acoes calculadas pelo CODIGO:
  REMIND (sempre);
  FREE_SHIPPING se subtotal >= minimo configurado (default 1500.00); o sinal
  de frete alto (>15% do subtotal) vira hint, nao amplia a regra;
  DISCOUNT_3PCT so se a empresa tem >= 1 pedido PAGO anterior E existe ao
  menos uma linha SEM preco negociado (FIXED_PRICE); nunca acumula;
  ESCALATE_HUMAN se subtotal >= limite (default 20000.00) ou sinal de risco.
- Sinais (reason hints) calculados em codigo: frete/subtotal, estoque baixo,
  item removido recentemente, valor abaixo do minimo de frete gratis,
  historico de compra.
- Limites de tentativa: no maximo 1 a cada 7 dias e 2 por ESTADO do carrinho
  (`last_activity_at`); parar se o carrinho mudou ou virou pedido.

Funcoes puras: sem I/O, sem framework, sem LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

MIN_IDLE_HOURS = 24
MAX_IDLE_DAYS = 7
FREE_SHIPPING_RATIO = Decimal("0.15")
DISCOUNT_PERCENT = Decimal("3.00")
MAX_ATTEMPTS_PER_STATE = 2
MIN_DAYS_BETWEEN_ATTEMPTS = 7


class RecoveryAction(StrEnum):
    REMIND = "REMIND"
    FREE_SHIPPING = "FREE_SHIPPING"
    DISCOUNT_3PCT = "DISCOUNT_3PCT"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class RecoveryReason(StrEnum):
    """reason_code estavel (audit/metrica); o LLM escolhe DENTRE estes."""

    CART_IDLE = "cart_idle"
    HIGH_SHIPPING_SHARE = "high_shipping_share"
    ABOVE_FREE_SHIPPING_MIN = "above_free_shipping_min"
    BELOW_FREE_SHIPPING_MIN = "below_free_shipping_min"
    REPEAT_CUSTOMER = "repeat_customer"
    FIRST_ORDER = "first_order"
    HIGH_VALUE = "high_value"
    RISK_SIGNAL = "risk_signal"
    LOW_STOCK = "low_stock"
    ITEM_REMOVED = "item_removed"


@dataclass(frozen=True, kw_only=True)
class RecoveryConfig:
    """Limiares configuraveis (Settings), com defaults de produto."""

    free_shipping_min_brl: Decimal = Decimal("1500.00")
    escalate_min_brl: Decimal = Decimal("20000.00")


@dataclass(frozen=True, kw_only=True)
class CartSnapshot:
    """Retrato calculado pelo CODIGO a partir do Postgres (sem PII no LLM)."""

    item_count: int
    subtotal: Decimal
    shipping_total: Decimal
    non_negotiated_subtotal: Decimal
    company_paid_orders: int
    last_activity_at: datetime
    has_order_after_activity: bool
    opted_out: bool
    low_stock_items: int = 0
    item_removed_recently: bool = False
    risk_signal: bool = False


@dataclass(frozen=True, kw_only=True)
class RecoveryPolicy:
    """Saida deterministica do no `policy` do grafo."""

    eligible: bool
    stop_reason: str | None
    eligible_actions: tuple[RecoveryAction, ...]
    reason_hints: tuple[RecoveryReason, ...]


def evaluate_recovery(
    snapshot: CartSnapshot,
    *,
    config: RecoveryConfig,
    now: datetime,
    last_attempt_at: datetime | None,
    attempts_for_state: int,
) -> RecoveryPolicy:
    """Elegibilidade + acoes permitidas + hints (tudo em codigo)."""
    stop_reason = _stop_reason(
        snapshot,
        now=now,
        last_attempt_at=last_attempt_at,
        attempts_for_state=attempts_for_state,
    )
    if stop_reason is not None:
        return RecoveryPolicy(
            eligible=False, stop_reason=stop_reason, eligible_actions=(), reason_hints=()
        )

    hints = _reason_hints(snapshot, config=config)
    actions: list[RecoveryAction] = [RecoveryAction.REMIND]
    if snapshot.subtotal >= config.free_shipping_min_brl:
        actions.append(RecoveryAction.FREE_SHIPPING)
    if snapshot.company_paid_orders >= 1 and snapshot.non_negotiated_subtotal > 0:
        actions.append(RecoveryAction.DISCOUNT_3PCT)
    if snapshot.subtotal >= config.escalate_min_brl or snapshot.risk_signal:
        actions.append(RecoveryAction.ESCALATE_HUMAN)
    return RecoveryPolicy(
        eligible=True,
        stop_reason=None,
        eligible_actions=tuple(actions),
        reason_hints=hints,
    )


def _stop_reason(
    snapshot: CartSnapshot,
    *,
    now: datetime,
    last_attempt_at: datetime | None,
    attempts_for_state: int,
) -> str | None:
    if snapshot.opted_out:
        return "opt_out"
    if snapshot.item_count <= 0:
        return "cart_empty"
    if snapshot.has_order_after_activity:
        return "order_after_activity"
    idle = now - snapshot.last_activity_at
    if idle < timedelta(hours=MIN_IDLE_HOURS):
        return "not_idle_enough"
    if idle > timedelta(days=MAX_IDLE_DAYS):
        return "too_old"
    if attempts_for_state >= MAX_ATTEMPTS_PER_STATE:
        return "attempts_exhausted_for_state"
    if last_attempt_at is not None and now - last_attempt_at < timedelta(
        days=MIN_DAYS_BETWEEN_ATTEMPTS
    ):
        return "cooldown_7_days"
    return None


def _reason_hints(snapshot: CartSnapshot, *, config: RecoveryConfig) -> tuple[RecoveryReason, ...]:
    hints: list[RecoveryReason] = [RecoveryReason.CART_IDLE]
    if snapshot.subtotal > 0 and (
        snapshot.shipping_total / snapshot.subtotal > FREE_SHIPPING_RATIO
    ):
        hints.append(RecoveryReason.HIGH_SHIPPING_SHARE)
    if snapshot.subtotal >= config.free_shipping_min_brl:
        hints.append(RecoveryReason.ABOVE_FREE_SHIPPING_MIN)
    else:
        hints.append(RecoveryReason.BELOW_FREE_SHIPPING_MIN)
    hints.append(
        RecoveryReason.REPEAT_CUSTOMER
        if snapshot.company_paid_orders >= 1
        else RecoveryReason.FIRST_ORDER
    )
    if snapshot.low_stock_items > 0:
        hints.append(RecoveryReason.LOW_STOCK)
    if snapshot.item_removed_recently:
        hints.append(RecoveryReason.ITEM_REMOVED)
    if snapshot.risk_signal:
        hints.append(RecoveryReason.RISK_SIGNAL)
    if snapshot.subtotal >= config.escalate_min_brl:
        hints.append(RecoveryReason.HIGH_VALUE)
    return tuple(hints)
