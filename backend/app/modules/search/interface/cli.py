"""CLI de manutencao do indice de busca (one-off, role de runtime).

Comandos:
    python -m app.modules.search.interface.cli reindex [--version N]
        [--batch-size N] [--dry-run]
    python -m app.modules.search.interface.cli reconcile

``reindex`` reconstroi o indice versionado a partir do PostgreSQL, valida a
contagem e troca o alias de forma atomica (o indice anterior permanece para
rollback). ``--dry-run`` nao toca no Elasticsearch: apenas conta o que seria
indexado (util quando o ES esta fora). Toda a execucao roda em um unico loop.
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
from app.modules.search.application.sync import (
    ReconcileReport,
    ReconcileSearchIndex,
    ReindexProducts,
    ReindexReport,
)
from app.modules.search.infrastructure.elasticsearch import build_product_index
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
    return parser


async def _run(settings: Settings, args: argparse.Namespace) -> dict[str, object]:
    index = build_product_index(settings)
    if index is None:
        return {"error": "elasticsearch_disabled"}
    engine = create_engine(settings)
    try:
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        reader = SqlAlchemyProductReader(uow_factory)
        report: ReindexReport | ReconcileReport
        if args.command == "reindex":
            default_version = settings.elasticsearch_index_version
            version = args.version if args.version is not None else default_version
            use_case = ReindexProducts(
                index=index, reader=reader, replicas=settings.elasticsearch_index_replicas
            )
            report = await use_case.run(
                version=version, batch_size=args.batch_size, dry_run=args.dry_run
            )
        else:
            reconcile = ReconcileSearchIndex(index=index, reader=reader, batch_size=args.batch_size)
            report = await reconcile.run()
        return cast("dict[str, object]", asdict(report))
    finally:
        await index.close()
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = asyncio.run(_run(get_settings(), args))
    print(json.dumps(payload, ensure_ascii=False))
    return 2 if "error" in payload else 0


if __name__ == "__main__":
    sys.exit(main())
