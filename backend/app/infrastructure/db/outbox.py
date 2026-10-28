"""Helper transacional de outbox de notificacoes.

Os repositorios de negocio (ordering/invoicing/payment) chamam
``enqueue_notification`` DENTRO da mesma transacao que persiste o evento, para
que a notificacao seja publicada de forma atomica com o commit (padrao outbox):
se a transacao falhar, a notificacao nao existe; se commitou, o worker a
despachara. O event_type e um contrato string estavel (ver notification.domain).
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT_NOTIFICATION = text(
    "INSERT INTO notifications (company_id, event_type, aggregate_id, channel, payload, status) "
    "VALUES (:company_id, :event_type, :aggregate_id, :channel, CAST(:payload AS jsonb), 'PENDING')"
)


async def enqueue_notification(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    event_type: str,
    aggregate_id: uuid.UUID,
    channel: str = "EMAIL",
    payload: dict[str, object] | None = None,
) -> None:
    """Registra uma notificacao PENDING na outbox, na transacao corrente.

    `channel`: "EMAIL" (padrao) ou "WHATSAPP" (exige opt-in; ver modulo
    notification). `payload`: slots de render (ex.: cart.recovery leva
    company_name/items_summary/offer_text — dados do backend, nunca do LLM).
    """
    await session.execute(
        _INSERT_NOTIFICATION,
        {
            "company_id": company_id,
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "channel": channel,
            "payload": json.dumps(payload) if payload is not None else None,
        },
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
