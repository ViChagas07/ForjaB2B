"""CLI de manutencao do indice de busca (one-off, role de runtime).

Comandos:
    python -m app.modules.search.interface.cli bootstrap [--version N]
    python -m app.modules.search.interface.cli reindex [--version N]
        [--batch-size N] [--dry-run]
    python -m app.modules.search.interface.cli reconcile
    python -m app.modules.search.interface.cli backfill-embeddings
        [--batch-size N] [--dry-run]

``bootstrap`` garante o indice versionado + alias (idempotente; nao exige
PostgreSQL). ``reindex`` reconstroi o indice a partir do PostgreSQL, valida a
contagem e troca o alias de forma atomica (o anterior permanece para rollback).
``backfill-embeddings`` gera/atualiza os vetores (idempotente por
``content_hash``). ``--dry-run`` nao escreve. Toda a execucao roda em um loop.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from typing import cast

from app.core.config import Settings, get_settings
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.search.application.embeddings_backfill import BackfillEmbeddings
from app.modules.search.application.errors import SearchIndexError
from app.modules.search.application.sync import (
    ReconcileReport,
    ReconcileSearchIndex,
    ReindexProducts,
    ReindexReport,
)
from app.modules.search.infrastructure.elasticsearch import build_product_index
from app.modules.search.infrastructure.embeddings import build_embedding_provider
from app.modules.search.infrastructure.pgvector_store import PgVectorStore
from app.modules.search.infrastructure.reader import SqlAlchemyProductReader


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


async def _run(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    if args.command == "bootstrap":
        return await _bootstrap(settings, args)
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
        try:
            report: ReindexReport | ReconcileReport
            if args.command == "reindex":
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
            else:
                reconcile = ReconcileSearchIndex(
                    index=index, reader=reader, batch_size=args.batch_size
                )
                report = await reconcile.run()
        except SearchIndexError as exc:
            # Falha visivel (rejeicao no bulk / contagem divergente): saida != 0.
            return {"error": f"{args.command}_failed", "detail": str(exc)}
        finally:
            await index.close()
        payload = cast("dict[str, object]", asdict(report))
        if isinstance(report, ReconcileReport) and report.rejected:
            payload["error"] = "reconcile_rejected"
            payload["detail"] = f"{report.rejected} documento(s) rejeitado(s) pelo Elasticsearch"
        return payload
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = asyncio.run(_run(get_settings(), args))
    print(json.dumps(payload, ensure_ascii=False))
    return 2 if "error" in payload else 0


if __name__ == "__main__":
    sys.exit(main())
