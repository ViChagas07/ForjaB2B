"""Job Celery do agente de recuperacao de carrinho (FASE 4).

Roda a cada 15 min (beat, fila default). Processa em LOTES: enumera tenants
com carrinhos parados entre 24h e 7 dias (funcao SECURITY DEFINER
``app.list_recovery_tenants``) e, por tenant (contexto RLS proprio), avalia os
candidatos e executa o grafo fixo. Idempotente: cooldown de 7 dias + 2
tentativas por estado do carrinho (last_activity_at) e lock consultivo do
PostgreSQL impede duplicidade entre workers. Kill switch: com
AI_AGENTS_ENABLED=false o LLM nem e construido — o agente degrada para
REMIND deterministico sem nota.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.domain.shipping import compute_shipping, compute_total_weight
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.application.ports import ResilientLLM
from app.modules.ai.application.recovery import (
    CartRecoveryGraph,
    RecoveryPersistRequest,
    offer_text_for,
)
from app.modules.ai.domain.recovery import (
    CartSnapshot,
    RecoveryAction,
    RecoveryConfig,
    RecoveryReason,
)
from app.modules.ai.infrastructure.llm_openai import build_langchain_llm
from app.modules.ai.infrastructure.recovery import (
    SqlAlchemyRecoveryContext,
    SqlAlchemyRecoveryRepository,
)
from app.modules.cart.application.cart import CartService
from app.modules.cart.infrastructure.repository import SqlAlchemyCartRepository
from app.modules.search.infrastructure.lock import PostgresAdvisoryLock
from app.tasks.celery_app import celery_app

RECOVERY_LOCK_KEY = "forja:cart:recovery"
_DEFAULT_LOCALE = "pt-BR"


@celery_app.task(name="app.tasks.cart_recovery.run_cart_recovery")
def run_cart_recovery() -> int:
    return asyncio.run(_run(get_settings()))


async def _run(settings: Settings) -> int:
    engine = create_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        cart_service = CartService(repository=SqlAlchemyCartRepository(uow_factory))
        context = SqlAlchemyRecoveryContext(uow_factory)
        repository = SqlAlchemyRecoveryRepository(uow_factory)
        graph = CartRecoveryGraph(
            llm=_build_llm(settings),
            persist_port=repository,
            config=RecoveryConfig(
                free_shipping_min_brl=settings.cart_recovery_free_shipping_min_brl,
                escalate_min_brl=settings.cart_recovery_escalate_min_brl,
            ),
            ai_enabled=settings.ai_agents_enabled,
        )

        lock = PostgresAdvisoryLock(engine, key=RECOVERY_LOCK_KEY)
        if not await lock.try_acquire():
            return 0
        try:
            return await _run_locked(settings, context, graph, cart_service)
        finally:
            await lock.release()
    finally:
        await engine.dispose()


def _build_llm(settings: Settings) -> ResilientLLM | None:
    """LLM so quando habilitado e configurado (kill switch por padrao)."""
    if not settings.ai_agents_enabled or not settings.llm_ready:
        return None
    return ResilientLLM(build_langchain_llm(settings), timeout_seconds=settings.llm_timeout_s)


async def _run_locked(
    settings: Settings,
    context: SqlAlchemyRecoveryContext,
    graph: CartRecoveryGraph,
    cart_service: CartService,
) -> int:
    now = datetime.now(UTC)
    tenants = await context.list_tenants(limit=settings.cart_recovery_tenant_batch)
    sent = 0
    for company_id in tenants:
        company_name = await context.company_name(company_id)
        candidates = await context.list_candidates(
            company_id, now=now, limit=settings.cart_recovery_cart_batch
        )
        for candidate in candidates:
            outcome = await _process_candidate(
                candidate,
                company_id=company_id,
                company_name=company_name,
                context=context,
                graph=graph,
                cart_service=cart_service,
                now=now,
            )
            if outcome:
                sent += 1
    return sent


async def _process_candidate(
    candidate: dict[str, Any],
    *,
    company_id: uuid.UUID,
    company_name: str,
    context: SqlAlchemyRecoveryContext,
    graph: CartRecoveryGraph,
    cart_service: CartService,
    now: datetime,
) -> bool:
    cart_id = candidate["cart_id"]
    user_id = candidate["user_id"]
    last_activity_at = candidate["last_activity_at"]
    subtotal, shipping, non_negotiated, summary = await _cart_basis(
        cart_service, company_id, user_id
    )
    snapshot = CartSnapshot(
        item_count=int(candidate["item_count"]),
        subtotal=subtotal,
        shipping_total=shipping,
        non_negotiated_subtotal=non_negotiated,
        company_paid_orders=int(candidate["paid_orders"]),
        last_activity_at=last_activity_at,
        has_order_after_activity=bool(candidate["order_after"]),
        opted_out=bool(candidate["opted_out"]),
        low_stock_items=0,  # catalogo nao tem coluna de estoque (hint neutro)
        item_removed_recently=_removed_recently(last_activity_at, candidate["last_item_touch"]),
        risk_signal=bool(candidate["risk"]),
    )
    attempts, last_attempt_at = await context.attempts_for_state(
        company_id, cart_id, last_activity_at
    )

    def persist_request(
        action: RecoveryAction, reason: RecoveryReason, note: str, verdict: str
    ) -> RecoveryPersistRequest:
        return RecoveryPersistRequest(
            cart_id=cart_id,
            company_id=company_id,
            user_id=user_id,
            locale=_DEFAULT_LOCALE,
            company_name=company_name,
            items_summary=summary,
            action=action,
            reason_code=reason,
            note=note,
            offer_text=offer_text_for(action, _DEFAULT_LOCALE),
            guard_verdict=verdict,
        )

    outcome = await graph.run(
        snapshot=snapshot,
        locale=_DEFAULT_LOCALE,
        last_attempt_at=last_attempt_at,
        attempts_for_state=attempts,
        persist_request=persist_request,
    )
    return outcome is not None


async def _cart_basis(
    cart_service: CartService, company_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Decimal, Decimal, Decimal, str]:
    """(subtotal, frete simulado, subtotal sem preco negociado, resumo de itens).

    Roda na raiz de composicao (task) para o modulo ai nao importar o cart.
    """
    view = await cart_service.get_cart(company_id, user_id, _DEFAULT_LOCALE)
    lines: list[str] = []
    weights: list[tuple[int, Decimal | None]] = []
    non_negotiated = Decimal("0.00")
    for item in view.items:
        lines.append(f"- {item.quantity}x {item.name} ({item.sku})")
        weights.append((item.quantity, item.weight_kg))
        if not item.is_negotiated:
            non_negotiated += item.line_total
    shipping = compute_shipping(total_weight_kg=compute_total_weight(weights))
    return view.subtotal, shipping, non_negotiated, "\n".join(lines)[:500]


def _removed_recently(last_activity_at: datetime, last_item_touch: datetime | None) -> bool:
    """Heuristica determinista (hint apenas): ultima atividade nao tocou itens.

    Como toda operacao de item toca last_activity_at E cart_items, se a
    atividade e mais recente que o ultimo toque de item, o ultimo gesto foi
    remover/limpar — sinal de friccao, nunca muda a acao por si so.
    """
    if last_item_touch is None:
        return True
    return (last_activity_at - last_item_touch) > timedelta(minutes=1) and (
        last_activity_at < datetime.now(UTC) + timedelta(seconds=1)
    )
