"""CLI de manutencao do indice de busca (one-off, role de runtime).

Comandos:
    python -m app.modules.search.interface.cli bootstrap [--version N]
    python -m app.modules.search.interface.cli reindex [--version N]
        [--batch-size N] [--dry-run]
    python -m app.modules.search.interface.cli reconcile
    python -m app.modules.search.interface.cli backfill-embeddings
        [--batch-size N] [--dry-run]
    python -m app.modules.search.interface.cli outbox list-dead [--limit N]
    python -m app.modules.search.interface.cli outbox requeue <id|--all> [--yes]
    python -m app.modules.search.interface.cli prune-indices [--keep N]
        [--dry-run] [--yes]

``bootstrap`` garante o indice versionado + alias (idempotente; nao exige
PostgreSQL). ``reindex`` reconstroi o indice a partir do PostgreSQL, valida a
contagem e troca o alias de forma atomica (o anterior permanece para rollback).
``backfill-embeddings`` gera/atualiza os vetores (idempotente por
``content_hash``). ``--dry-run`` nao escreve. Toda a execucao roda em um loop.
O subcomando ``outbox`` opera a dead-letter (listar/reprocessar) e exige
``--yes`` para o reprocessamento em massa.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
import uuid
from dataclasses import asdict
from typing import cast

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.embeddings_backfill import BackfillEmbeddings
from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.prune import PruneSearchIndices
from app.modules.search.application.sync import ReindexProducts, ReindexReport
from app.modules.search.infrastructure.elasticsearch import build_product_index
from app.modules.search.infrastructure.embeddings import build_embedding_provider
from app.modules.search.infrastructure.outbox_repository import (
    SqlAlchemySearchOutboxRepository,
)
from app.modules.search.infrastructure.pgvector_store import PgVectorStore
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader
from app.modules.search.infrastructure.reconcile import ReconcileService

_logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="search", description="Manutencao do indice de busca.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reindex = subparsers.add_parser("reindex", help="Reconstroi o indice a partir do PostgreSQL.")
    reindex.add_argument("--version", type=int, default=None, help="Versao do indice.")
    reindex.add_argument("--batch-size", type=int, default=500, help="Tamanho do lote.")
    reindex.add_argument("--dry-run", action="store_true", help="Somente conta (nao toca no ES).")

    reconcile = subparsers.add_parser("reconcile", help="Corrige divergencias Postgres x indice.")
    reconcile.add_argument("--batch-size", type=int, default=500, help="Tamanho do lote.")

    backfill = subparsers.add_parser(
        "backfill-embeddings", help="Gera/atualiza embeddings vetoriais (idempotente)."
    )
    backfill.add_argument("--batch-size", type=int, default=256, help="Tamanho do lote.")
    backfill.add_argument("--dry-run", action="store_true", help="Somente conta (nao grava).")

    bootstrap = subparsers.add_parser(
        "bootstrap", help="Cria o indice versionado e aponta o alias (idempotente)."
    )
    bootstrap.add_argument("--version", type=int, default=None, help="Versao do indice.")

    outbox = subparsers.add_parser("outbox", help="Consulta/reprocessa eventos dead-letter.")
    outbox_sub = outbox.add_subparsers(dest="outbox_command", required=True)
    list_dead = outbox_sub.add_parser("list-dead", help="Lista eventos em DEAD_LETTERED.")
    list_dead.add_argument(
        "--limit", type=int, default=100, help="Maximo de eventos (default: 100)."
    )
    requeue = outbox_sub.add_parser("requeue", help="Devolve evento(s) dead-letter para PENDING.")
    requeue.add_argument("event_id", nargs="?", help="ID do evento (omita com --all).")
    requeue.add_argument("--all", action="store_true", help="Reprocessa todos os eventos mortos.")
    requeue.add_argument(
        "--yes",
        action="store_true",
        help="Confirmacao explicita obrigatoria com --all.",
    )

    prune = subparsers.add_parser(
        "prune-indices", help="Remove versoes antigas do indice (preserva o alias)."
    )
    prune.add_argument("--keep", type=int, default=2, help="Versoes mais recentes a manter.")
    prune.add_argument("--dry-run", action="store_true", help="Somente lista o que seria removido.")
    prune.add_argument("--yes", action="store_true", help="Confirmacao obrigatoria sem --dry-run.")
    return parser


async def _bootstrap(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    """Garante o indice versionado + alias (idempotente); nao exige PostgreSQL."""
    index = build_product_index(settings)
    if index is None:
        return {"error": "elasticsearch_disabled"}
    try:
        version = args.version if args.version is not None else settings.elasticsearch_index_version
        name = await index.create_versioned_index(
            version=version, replicas=settings.elasticsearch_index_replicas
        )
        await index.swap_alias(index_name=name)
        return {"index": name, "alias": index.alias, "documents": await index.count(target=name)}
    finally:
        await index.close()


async def _outbox_command(
    repository: SqlAlchemySearchOutboxRepository, args: argparse.Namespace
) -> dict[str, object]:
    """Lista ou Reprocessa eventos dead-letter com auditoria em log estruturado."""
    if args.outbox_command == "list-dead":
        events = await repository.list_dead(limit=args.limit)
        return {
            "status": "ok",
            "count": len(events),
            "events": [
                {
                    "id": str(event.id),
                    "aggregate_id": str(event.aggregate_id),
                    "event_type": event.event_type,
                    "version": event.version,
                    "attempts": event.attempts,
                    "last_error": event.last_error,
                    "created_at": event.created_at.isoformat(),
                    "updated_at": event.updated_at.isoformat(),
                }
                for event in events
            ],
        }

    operator = getpass.getuser()
    if args.all:
        if not args.yes:
            return {
                "error": "confirmation_required",
                "detail": "requeue --all exige --yes (confirmacao explicita)",
            }
        count = await repository.requeue_all()
        _logger.info(
            "search_outbox_requeued",
            scope="all",
            count=count,
            operator=operator,
        )
        return {"status": "ok", "scope": "all", "requeued": count}

    if not args.event_id:
        return {"error": "event_id_required", "detail": "informe o id ou use --all --yes"}
    try:
        event_id = uuid.UUID(args.event_id)
    except ValueError:
        return {"error": "invalid_event_id", "detail": "o id deve ser um UUID"}
    found = await repository.requeue(event_id)
    if not found:
        return {"error": "dead_event_not_found", "detail": "evento dead-letter nao encontrado"}
    _logger.info(
        "search_outbox_requeued",
        scope="one",
        event_id=str(event_id),
        operator=operator,
    )
    return {"status": "ok", "scope": "one", "event_id": str(event_id), "requeued": 1}


async def _run_reconcile(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    """Reconcilia com advisory lock; a segunda instancia sai como skipped."""
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        run = await ReconcileService(
            settings=settings, engine=engine, uow_factory=uow_factory
        ).run()
        if run.status == "disabled":
            return {"error": "elasticsearch_disabled"}
        if run.status == "skipped":
            return {"status": "skipped", "reason": "reconcile_already_running"}
        if run.report is None:
            return {"error": "reconcile_failed"}
        report = run.report
        payload = cast("dict[str, object]", asdict(report))
        if report.rejected:
            payload["error"] = "reconcile_rejected"
            payload["detail"] = f"{report.rejected} documento(s) rejeitado(s) pelo Elasticsearch"
        return payload
    finally:
        await engine.dispose()


async def _run_prune(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    """Limpa versoes antigas; exige --yes fora do dry-run."""
    if args.keep < 1:
        return {"error": "invalid_keep", "detail": "--keep deve ser >= 1"}
    if not args.dry_run and not args.yes:
        return {
            "error": "confirmation_required",
            "detail": "prune-indices exige --yes (ou use --dry-run)",
        }
    index = build_product_index(settings)
    if index is None:
        return {"error": "elasticsearch_disabled"}
    try:
        report = await PruneSearchIndices(index=index, keep=args.keep).run(dry_run=args.dry_run)
        return cast("dict[str, object]", asdict(report))
    finally:
        await index.close()


async def _run(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    if args.command == "bootstrap":
        return await _bootstrap(settings, args)
    if args.command == "outbox":
        return await _run_outbox(settings, args)
    if args.command == "prune-indices":
        return await _run_prune(settings, args)
    if args.command == "reconcile":
        return await _run_reconcile(settings, args)
    return await _run_db(settings, args)


async def _run_outbox(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    """Comandos de outbox nao precisam do indice; so de PostgreSQL."""
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        return await _outbox_command(SqlAlchemySearchOutboxRepository(uow_factory), args)
    finally:
        await engine.dispose()


async def _run_db(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        reader = SqlAlchemyProductReader(uow_factory)
        if args.command == "backfill-embeddings":
            provider = build_embedding_provider(settings)
            if provider is None:
                return {"error": "embeddings_disabled"}
            embedding_report = await BackfillEmbeddings(
                provider=provider,
                store=PgVectorStore(uow_factory),
                reader=reader,
                batch_size=args.batch_size,
            ).run(dry_run=args.dry_run)
            return cast("dict[str, object]", asdict(embedding_report))
        index = build_product_index(settings)
        if index is None:
            return {"error": "elasticsearch_disabled"}
        report: ReindexReport
        try:
            default_version = settings.elasticsearch_index_version
            version = args.version if args.version is not None else default_version
            use_case = ReindexProducts(
                index=index,
                reader=reader,
                replicas=settings.elasticsearch_index_replicas,
                count_tolerance=settings.search_reindex_count_tolerance,
            )
            report = await use_case.run(
                version=version, batch_size=args.batch_size, dry_run=args.dry_run
            )
        except SearchIndexError as exc:
            # Falha visivel (rejeicao no bulk / contagem divergente): saida != 0.
            return {"error": f"{args.command}_failed", "detail": str(exc)}
        finally:
            await index.close()
        return cast("dict[str, object]", asdict(report))
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = asyncio.run(_run(get_settings(), args))
    print(json.dumps(payload, ensure_ascii=False))
    return 2 if "error" in payload else 0


if __name__ == "__main__":
    sys.exit(main())
