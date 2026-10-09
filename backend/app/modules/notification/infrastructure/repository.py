"""Repositorio SQLAlchemy do contexto de notificacao (outbox + destinatario).

A outbox ``notifications`` e tenant-scoped (RLS). O despacho e feito por tenant
(``DispatchOutbox.dispatch(company_id)``); a enumeracao cross-tenant das
notificacoes pendentes e feita pelo worker via a funcao SECURITY DEFINER
``app.list_due_notifications`` (ver docker/postgres e migration 0010).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.notification.application.ports import OutboxView, RecipientView
from app.modules.notification.domain.enums import NotificationStatus

_LIST_DUE = text(
    "SELECT id, company_id, event_type, aggregate_id, payload, status, attempts, created_at "
    "FROM notifications WHERE company_id = :company_id AND "
    "(status = 'PENDING' OR (status = 'FAILED' AND attempts < :max_attempts)) "
    "ORDER BY created_at, id LIMIT :limit"
)
_LIST_DUE_TENANTS = text("SELECT company_id FROM app.list_due_notifications(:limit, :max_attempts)")
_RESOLVE_BUYER = text(
    "SELECT u.id AS user_id, u.email FROM orders o "
    "JOIN users u ON u.id = o.buyer_user_id "
    "WHERE o.id = :order_id AND o.company_id = :company_id"
)
_SELECT_PREFERENCE = text(
    "SELECT enabled FROM notification_preferences "
    "WHERE company_id = :company_id AND user_id = :user_id AND channel = 'EMAIL'"
)
_UPDATE_STATUS = text(
    "UPDATE notifications SET status = :status, error = :error, attempts = attempts + 1, "
    "sent_at = :sent_at, updated_at = now() WHERE id = :id AND company_id = :company_id"
)
_LIST_ALL = text(
    "SELECT id, company_id, event_type, aggregate_id, payload, status, attempts, created_at "
    "FROM notifications WHERE company_id = :company_id ORDER BY created_at DESC, id DESC"
)
_GET_ONE = text(
    "SELECT id, company_id, event_type, aggregate_id, payload, status, attempts, created_at "
    "FROM notifications WHERE id = :id AND company_id = :company_id"
)
_RESET = text(
    "UPDATE notifications SET status = 'PENDING', attempts = 0, error = NULL, "
    "sent_at = NULL, updated_at = now() WHERE id = :id AND company_id = :company_id"
)


def _to_view(row: Any) -> OutboxView:
    return OutboxView(
        id=row.id,
        company_id=row.company_id,
        event_type=row.event_type,
        aggregate_id=row.aggregate_id,
        payload=row.payload,
        status=row.status,
        attempts=row.attempts,
        created_at=row.created_at,
    )


class SqlAlchemyNotificationRepository:
    """Implementacao da porta NotificationRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def list_due(
        self, *, company_id: uuid.UUID, limit: int, max_attempts: int
    ) -> list[OutboxView]:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            rows = (
                await uow.session.execute(
                    _LIST_DUE,
                    {"company_id": company_id, "max_attempts": max_attempts, "limit": limit},
                )
            ).all()
            await uow.commit()
            return [_to_view(r) for r in rows]

    async def list_due_tenants(self, *, limit: int, max_attempts: int) -> set[uuid.UUID]:
        async with self._uow_factory.begin() as uow:
            rows = (
                await uow.session.execute(
                    _LIST_DUE_TENANTS,
                    {"limit": limit, "max_attempts": max_attempts},
                )
            ).all()
            await uow.commit()
            return {row.company_id for row in rows}

    async def resolve_recipient(
        self, *, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> RecipientView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            buyer = (
                await uow.session.execute(
                    _RESOLVE_BUYER, {"order_id": order_id, "company_id": company_id}
                )
            ).first()
            if buyer is None:
                await uow.commit()
                return None
            preference = (
                await uow.session.execute(
                    _SELECT_PREFERENCE, {"company_id": company_id, "user_id": buyer.user_id}
                )
            ).first()
            await uow.commit()
            opted_out = preference is not None and not bool(preference[0])
            return RecipientView(email=buyer.email, locale=None, opted_out=opted_out)

    async def mark(
        self,
        *,
        company_id: uuid.UUID,
        outbox_id: uuid.UUID,
        status: NotificationStatus,
        error: str | None = None,
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            sent_at = datetime.now(UTC) if status == NotificationStatus.SENT else None
            await uow.session.execute(
                _UPDATE_STATUS,
                {
                    "id": outbox_id,
                    "company_id": company_id,
                    "status": status.value,
                    "error": error,
                    "sent_at": sent_at,
                },
            )
            await uow.commit()

    async def list_notifications(self, company_id: uuid.UUID) -> list[OutboxView]:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            rows = (await uow.session.execute(_LIST_ALL, {"company_id": company_id})).all()
            await uow.commit()
            return [_to_view(r) for r in rows]

    async def get_notification(
        self, company_id: uuid.UUID, outbox_id: uuid.UUID
    ) -> OutboxView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(_GET_ONE, {"id": outbox_id, "company_id": company_id})
            ).first()
            await uow.commit()
            return None if row is None else _to_view(row)

    async def reset_for_resend(self, company_id: uuid.UUID, outbox_id: uuid.UUID) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(_RESET, {"id": outbox_id, "company_id": company_id})
            await uow.commit()
