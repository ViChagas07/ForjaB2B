"""Helper transacional de outbox de notificacoes.

Os repositorios de negocio (ordering/invoicing/payment) chamam
``enqueue_notification`` DENTRO da mesma transacao que persiste o evento, para
que a notificacao seja publicada de forma atomica com o commit (padrao outbox):
se a transacao falhar, a notificacao nao existe; se commitou, o worker a
despachara. O event_type e um contrato string estavel (ver notification.domain).
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT_NOTIFICATION = text(
    "INSERT INTO notifications (company_id, event_type, aggregate_id, channel, status) "
    "VALUES (:company_id, :event_type, :aggregate_id, 'EMAIL', 'PENDING')"
)


async def enqueue_notification(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    event_type: str,
    aggregate_id: uuid.UUID,
) -> None:
    """Registra uma notificacao PENDING na outbox, na transacao corrente."""
    await session.execute(
        _INSERT_NOTIFICATION,
        {"company_id": company_id, "event_type": event_type, "aggregate_id": aggregate_id},
    )
