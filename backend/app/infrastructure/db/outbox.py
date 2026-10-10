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


_INSERT_SEARCH_EVENT = text(
    "INSERT INTO search_outbox (aggregate_type, aggregate_id, event_type, version, status) "
    "VALUES (:aggregate_type, :aggregate_id, :event_type, :version, 'PENDING')"
)


async def enqueue_search_event(
    session: AsyncSession,
    *,
    aggregate_id: uuid.UUID,
    event_type: str,
    version: int,
    aggregate_type: str = "product",
) -> None:
    """Registra um evento de sincronizacao de busca na transacao corrente.

    Deve ser chamado DENTRO da mesma transacao/UoW que altera o produto (padrao
    outbox): se a transacao falhar, o evento nao existe; se commitou, o worker
    aplicara no indice. Ainda nao ha caminho de escrita de catalogo no runtime
    (Fase 3): este helper e o contrato pronto para o backoffice.
    """
    await session.execute(
        _INSERT_SEARCH_EVENT,
        {
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "version": version,
        },
    )
