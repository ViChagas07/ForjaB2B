"""Limpeza diaria das conversas de chat expiradas (FASE 5a).

Segue o padrao do dispatch_outbox: o worker monta engine/UoW/repositorio de
forma independente da API e chama a funcao SECURITY DEFINER
``app.delete_expired_chat_conversations`` (criada no bootstrap), que remove
cross-tenant por TTL (`AI_CONVERSATION_TTL_DAYS`). Mensagens caem por CASCADE.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.ai.infrastructure.chat_repository import SqlAlchemyConversationRepository
from app.tasks.celery_app import celery_app

DEFAULT_CLEANUP_BATCH = 500


@celery_app.task(name="app.tasks.ai_chat.cleanup_chat_conversations")
def cleanup_chat_conversations() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        repository = SqlAlchemyConversationRepository(uow_factory)
        return asyncio.run(
            repository.delete_expired(limit=settings.ai_chat_cleanup_batch or DEFAULT_CLEANUP_BATCH)
        )
    finally:
        asyncio.run(engine.dispose())
