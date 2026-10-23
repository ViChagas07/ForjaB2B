#!/usr/bin/env python3
"""Backup logico do PostgreSQL de desenvolvimento (pg_dump custom).

O arquivo e gravado fora do volume do banco (por padrao ``backups/`` na raiz do
repositorio), com timestamp UTC e validacao de tamanho/formato. A rotacao
remove apenas arquivos do padrao ``forja_db_<timestamp>.dump``.

Nenhuma credencial vai em argumentos: o ``pg_dump`` roda dentro do container e
usa a autenticacao local do proprio PostgreSQL (trust no socket local do
Compose). Variaveis de ambiente opcionais:

* ``BACKUP_DIR``: diretorio de saida (default: ``./backups``);
* ``BACKUP_RETENTION``: quantidade de backups mantidos (default: 7).

Uso:
    python scripts/backup_db.py [--dir DIR] [--keep N] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from ops_common import (
    REPO_ROOT,
    PostgresConfig,
    backup_name,
    print_report,
    rotate_backups,
    run_to_file,
    utc_now,
    validate_backup_file,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dump(config: PostgresConfig, database: str, destination: Path) -> None:
    run_to_file(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            # pg_dump precisa ler TODAS as linhas; as tabelas de tenant usam
            # FORCE RLS e a role forja_admin veria zero linhas. Em producao o
            # backup deve usar uma role dedicada com BYPASSRLS ou o backup
            # gerenciado do provedor.
            "-U",
            config.bootstrap_user,
            "-d",
            database,
            "--format=custom",
            "--compress=6",
            "--no-password",
        ],
        destination,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup logico (pg_dump custom) com rotacao.")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("BACKUP_DIR", str(REPO_ROOT / "backups"))),
        help="Diretorio de saida (fora do volume do PostgreSQL).",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=int(os.environ.get("BACKUP_RETENTION", "7")),
        help="Quantidade de backups mantidos apos a rotacao (default: 7).",
    )
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio em JSON.")
    args = parser.parse_args(argv)
    if args.keep < 1:
        parser.error("--keep deve ser >= 1")

    started = time.monotonic()
    config = PostgresConfig.from_environment()
    directory = args.dir.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / backup_name()
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory, prefix=".forja_dump_", suffix=".tmp", delete=False
        ) as temp:
            temp_path = Path(temp.name)
        _dump(config, config.database, temp_path)
        size = validate_backup_file(temp_path)
        os.replace(temp_path, target)
        temp_path = None
        removed = rotate_backups(directory, keep=args.keep, database=config.database)
        report = {
            "status": "ok",
            "database": config.database,
            "file": str(target),
            "bytes": size,
            "sha256": _sha256(target),
            "created_at": utc_now().isoformat(),
            "retention": args.keep,
            "removed": [path.name for path in removed],
            "seconds": round(time.monotonic() - started, 2),
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_report(
                "BACKUP: OK",
                [
                    f"banco: {report['database']}",
                    f"arquivo: {report['file']} ({size} bytes)",
                    f"sha256: {report['sha256']}",
                    f"rotacao: {len(removed)} removido(s), retencao {args.keep}",
                    f"tempo: {report['seconds']}s",
                ],
            )
        return 0
    except Exception as exc:  # noqa: BLE001 - relatorio e exit code
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        message = f"backup falhou: {exc}"
        if args.json:
            print(json.dumps({"status": "failed", "error": message}, ensure_ascii=False))
        else:
            print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
