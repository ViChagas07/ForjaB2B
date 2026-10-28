"""Persistencia e contexto do agente de recuperacao (infrastructure).

- `SqlAlchemyRecoveryContext`: carrega tenants/candidatos por tenant (RLS) e o
  nome da empresa; monta o snapshot SEM enviar PII ao LLM.
- `SqlAlchemyRecoveryRepository.persist`: em UMA transacao, cria a oferta (se
  preciso), enfileira o evento `cart.recovery` na outbox, grava a tentativa e o
  registro em `agent_audit_log` (payload com hash/prefixo da nota — nunca o
  texto completo do usuario).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.outbox import enqueue_notification
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.application.recovery import RecoveryPersistRequest
from app.modules.ai.domain.audit_payload import build_audit_payload
from app.modules.ai.domain.recovery import RecoveryAction

OFFER_TTL_HOURS = 72
DISCOUNT_PERCENT = Decimal("3.00")

_LIST_TENANTS = text("SELECT company_id FROM app.list_recovery_tenants(:limit)")
_SELECT_CANDIDATES = text(
    "SELECT c.id AS cart_id, c.user_id, c.last_activity_at, "
    " (SELECT count(*) FROM cart_items ci WHERE ci.cart_id = c.id) AS item_count, "
    " EXISTS(SELECT 1 FROM orders o WHERE o.company_id = c.company_id "
    "   AND o.buyer_user_id = c.user_id AND o.created_at > c.last_activity_at) AS order_after, "
    " EXISTS(SELECT 1 FROM notification_preferences np WHERE np.company_id = c.company_id "
    "   AND np.user_id = c.user_id AND np.channel = 'EMAIL' AND np.enabled = false) AS opted_out, "
    " (SELECT count(*) FROM orders o WHERE o.company_id = c.company_id "
    "   AND o.status = 'PAID') AS paid_orders, "
    " (SELECT max(ci.updated_at) FROM cart_items ci WHERE ci.cart_id = c.id) AS last_item_touch, "
    " EXISTS(SELECT 1 FROM credit_accounts ca WHERE ca.company_id = c.company_id "
    "   AND ca.credit_limit <= (SELECT COALESCE(SUM(ce.amount), 0) FROM credit_entries ce "
    "     WHERE ce.company_id = ca.company_id)) AS risk "
    "FROM carts c "
    "WHERE c.last_activity_at <= :older_than "
    "  AND c.last_activity_at >= :newer_than "
    "ORDER BY c.last_activity_at LIMIT :limit"
)
_SELECT_COMPANY_NAME = text("SELECT legal_name FROM companies WHERE id = :company_id")
_SELECT_ATTEMPTS = text(
    "SELECT count(*) AS total, max(created_at) AS last_at FROM cart_recovery_attempts "
    "WHERE cart_id = :cart_id AND created_at >= :state_started_at"
)
_INSERT_OFFER = text(
    "INSERT INTO cart_recovery_offers (company_id, cart_id, type, percent, expires_at) "
    "VALUES (:company_id, :cart_id, :type, :percent, :expires_at) RETURNING id"
)
_INSERT_ATTEMPT = text(
    "INSERT INTO cart_recovery_attempts (cart_id, company_id, user_id, status, reason_code, "
    "chosen_action, channel, offer_id, guard_verdict, sent_at) VALUES "
    "(:cart_id, :company_id, :user_id, :status, :reason_code, :chosen_action, 'EMAIL', "
    ":offer_id, :guard_verdict, now())"
)
_INSERT_AUDIT = text(
    "INSERT INTO agent_audit_log (agent, event, company_id, verdict, reason_code, payload) "
    "VALUES ('cart', 'recovery.attempt', :company_id, :verdict, :reason_code, "
    "CAST(:payload AS jsonb))"
)


class SqlAlchemyRecoveryContext:
    """Leitura dos candidatos (por tenant, dentro do contexto RLS).

    NAO importa o modulo cart (bounded contexts): a base de precos do carrinho
    (subtotal/frete/linhas negociadas/resumo) e calculada pelo JOB, que
    orquestra os modulos na raiz de composicao.
    """

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list_tenants(self, *, limit: int) -> list[uuid.UUID]:
        async with self._uow_factory.begin() as uow:
            rows = (await uow.session.execute(_LIST_TENANTS, {"limit": limit})).all()
            await uow.commit()
        return [row.company_id for row in rows]

    async def company_name(self, company_id: uuid.UUID) -> str:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(_SELECT_COMPANY_NAME, {"company_id": company_id})
            ).first()
            await uow.commit()
        return str(row[0]) if row else "Forja"

    async def list_candidates(
        self, company_id: uuid.UUID, *, now: datetime, limit: int
    ) -> list[dict[str, Any]]:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            rows = (
                await uow.session.execute(
                    _SELECT_CANDIDATES,
                    {
                        "older_than": now - timedelta(hours=24),
                        "newer_than": now - timedelta(days=7),
                        "limit": limit,
                    },
                )
            ).all()
            await uow.commit()
        return [dict(row._mapping) for row in rows]

    async def attempts_for_state(
        self, company_id: uuid.UUID, cart_id: uuid.UUID, state_started_at: datetime
    ) -> tuple[int, datetime | None]:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_ATTEMPTS,
                    {"cart_id": cart_id, "state_started_at": state_started_at},
                )
            ).first()
            await uow.commit()
        return (int(row.total), row.last_at) if row else (0, None)


class SqlAlchemyRecoveryRepository:
    """Persistencia do no `act` (uma transacao com RLS de tenant)."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def persist(self, request: RecoveryPersistRequest) -> uuid.UUID | None:
        tenant = TenantContext(company_id=request.company_id, user_id=request.user_id)
        async with self._uow_factory.begin(tenant) as uow:
            offer_id = await self._maybe_create_offer(uow, request)
            note_audit = build_audit_payload(request.note) if request.note else None
            await enqueue_notification(
                uow.session,
                company_id=request.company_id,
                event_type="cart.recovery",
                aggregate_id=request.cart_id,
                channel="EMAIL",
                payload={
                    "company_name": request.company_name,
                    "items_summary": request.items_summary,
                    "offer_text": request.offer_text,
                    "personal_note": request.note,
                    "locale": request.locale,
                },
            )
            await uow.session.execute(
                _INSERT_ATTEMPT,
                {
                    "cart_id": request.cart_id,
                    "company_id": request.company_id,
                    "user_id": request.user_id,
                    "status": "SENT",
                    "reason_code": request.reason_code.value,
                    "chosen_action": request.action.value,
                    "offer_id": offer_id,
                    "guard_verdict": request.guard_verdict,
                },
            )
            await uow.session.execute(
                _INSERT_AUDIT,
                {
                    "company_id": request.company_id,
                    "verdict": request.guard_verdict,
                    "reason_code": request.reason_code.value,
                    "payload": __import__("json").dumps(
                        {
                            "action": request.action.value,
                            "note": note_audit,
                        }
                    ),
                },
            )
            await uow.commit()
        return offer_id

    async def _maybe_create_offer(
        self, uow: Any, request: RecoveryPersistRequest
    ) -> uuid.UUID | None:
        if request.action not in (RecoveryAction.FREE_SHIPPING, RecoveryAction.DISCOUNT_3PCT):
            return None
        offer_type = (
            "FREE_SHIPPING"
            if request.action == RecoveryAction.FREE_SHIPPING
            else "PERCENT_DISCOUNT"
        )
        percent = DISCOUNT_PERCENT if offer_type == "PERCENT_DISCOUNT" else None
        return cast(
            uuid.UUID,
            (
                await uow.session.execute(
                    _INSERT_OFFER,
                    {
                        "company_id": request.company_id,
                        "cart_id": request.cart_id,
                        "type": offer_type,
                        "percent": percent,
                        "expires_at": datetime.now(UTC) + timedelta(hours=OFFER_TTL_HOURS),
                    },
                )
            ).scalar_one(),
        )
