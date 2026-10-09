"""Tarefa Celery de despacho da outbox de notificacoes.

Enumera os tenants com notificacoes pendentes (funcao SECURITY DEFINER
``app.list_due_notifications``) e despacha cada tenant com o seu proprio
contexto RLS. O worker monta engine/UoW/email de forma independente da API.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.notification.application.notification import DispatchOutbox
from app.modules.notification.infrastructure.email import SmtpEmailSender
from app.modules.notification.infrastructure.repository import SqlAlchemyNotificationRepository
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.notifications.dispatch_outbox")
def dispatch_outbox() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        repository = SqlAlchemyNotificationRepository(uow_factory)
        sender = SmtpEmailSender(
            host=settings.email_smtp_host,
            port=settings.email_smtp_port,
            from_email=settings.email_from,
        )
        use_case = DispatchOutbox(repository=repository, email_sender=sender)
        return asyncio.run(_dispatch(use_case, repository))
    finally:
        asyncio.run(engine.dispose())


async def _dispatch(use_case: DispatchOutbox, repository: SqlAlchemyNotificationRepository) -> int:
    tenants = await repository.list_due_tenants(limit=500, max_attempts=5)
    total = 0
    for company_id in tenants:
        total += await use_case.dispatch(company_id=company_id, limit=100)
    return total
