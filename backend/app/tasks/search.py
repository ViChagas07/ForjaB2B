"""Tarefas Celery da sincronizacao do indice de busca (Fase 3).

Reutiliza o Celery/RabbitMQ/Redis ja configurados (sem nova infraestrutura).
Se o Elasticsearch estiver indisponivel, o catalogo continua funcionando e os
eventos permanecem na outbox para reprocessamento (a tarefa falha e o beat
repete no proximo ciclo). Uma unica chamada a ``asyncio.run`` por execucao
(engine e cliente do ES sao abertos e fechados no mesmo loop).
"""

from __future__ import annotations

import asyncio

from app.core.config import Settings, get_settings
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.embeddings_backfill import BackfillEmbeddings, EmbeddingSync
from app.modules.search.application.sync import DispatchSearchOutbox, ReconcileSearchIndex
from app.modules.search.infrastructure.elasticsearch import build_product_index
from app.modules.search.infrastructure.embeddings import build_embedding_provider
from app.modules.search.infrastructure.outbox_repository import (
    SqlAlchemySearchOutboxRepository,
)
from app.modules.search.infrastructure.pgvector_store import PgVectorStore
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.search.dispatch_search_outbox")
def dispatch_search_outbox() -> int:
    """Aplica eventos pendentes da outbox no indice; devolve o total processado."""
    return asyncio.run(_run_dispatch(get_settings()))


async def _run_dispatch(settings: Settings) -> int:
    index = build_product_index(settings)
    if index is None:
        return 0
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        provider = build_embedding_provider(settings)
        embedding_sync = (
            EmbeddingSync(provider=provider, store=PgVectorStore(uow_factory))
            if provider is not None
            else None
        )
        use_case = DispatchSearchOutbox(
            index=index,
            reader=SqlAlchemyProductReader(uow_factory),
            outbox=SqlAlchemySearchOutboxRepository(uow_factory),
            max_attempts=settings.search_outbox_max_attempts,
            embedding_sync=embedding_sync,
        )
        report = await use_case.run(limit=100)
        return report.processed
    finally:
        await index.close()
        await engine.dispose()


@celery_app.task(name="app.tasks.search.backfill_search_embeddings")
def backfill_search_embeddings() -> int:
    """Backfill vetorial idempotente; devolve o total de embeddings gravados."""
    return asyncio.run(_run_backfill_embeddings(get_settings()))


async def _run_backfill_embeddings(settings: Settings) -> int:
    provider = build_embedding_provider(settings)
    if provider is None:
        return 0
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        report = await BackfillEmbeddings(
            provider=provider,
            store=PgVectorStore(uow_factory),
            reader=SqlAlchemyProductReader(uow_factory),
            batch_size=settings.embedding_batch_size,
        ).run()
        return report.embedded
    finally:
        await engine.dispose()


@celery_app.task(name="app.tasks.search.reconcile_search_index")
def reconcile_search_index() -> int:
    """Reconcilia Postgres x indice; devolve o total de correcoes."""
    return asyncio.run(_run_reconcile(get_settings()))


async def _run_reconcile(settings: Settings) -> int:
    index = build_product_index(settings)
    if index is None:
        return 0
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        use_case = ReconcileSearchIndex(
            index=index,
            reader=SqlAlchemyProductReader(uow_factory),
            batch_size=settings.elasticsearch_bulk_batch_size,
        )
        report = await use_case.run()
        return report.upserted + report.deleted
    finally:
        await index.close()
        await engine.dispose()
