#!/usr/bin/env python3
"""Drill de restauracao do ultimo backup em um banco descartavel.

1. valida o arquivo de backup (tamanho + magic ``PGDMP``);
2. registra as contagens do banco operacional (somente leitura);
3. cria ``forja_scratch_restore_*`` e restaura o dump com ``pg_restore``;
4. roda ``alembic current``/``alembic check`` no banco restaurado;
5. confere contagens das tabelas-chave e a presenca das extensoes;
6. confirma que o banco operacional nao mudou;
7. remove APENAS o banco descartavel que criou.

Uso:
    python scripts/restore_drill.py [--backup ARQUIVO] [--keep] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from ops_common import (
    OpsError,
    PostgresConfig,
    REPO_ROOT,
    alembic,
    create_scratch_database,
    drop_scratch_database,
    is_backup_name,
    psql,
    run_with_stdin_file,
    utc_now,
    validate_backup_file,
)

_KEY_COUNTS_SQL = """
SELECT 'products|' || count(*) FROM products
UNION ALL SELECT 'companies|' || count(*) FROM companies
UNION ALL SELECT 'users|' || count(*) FROM users
UNION ALL SELECT 'price_rules|' || count(*) FROM company_price_rules
UNION ALL SELECT 'translations|' || count(*) FROM product_translations
UNION ALL SELECT 'outbox|' || count(*) FROM search_outbox
"""

_REQUIRED_EXTENSIONS = frozenset({"vector", "unaccent", "pg_trgm", "pgcrypto", "uuid-ossp"})


def _latest_backup(directory: Path) -> Path:
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.startswith("forja_db_") and is_backup_name(path.name)
    ]
    if not candidates:
        raise OpsError(f"nenhum backup encontrado em {directory}")
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def _counts(config: PostgresConfig, database: str) -> dict[str, int]:
    raw = psql(config, database, _KEY_COUNTS_SQL, user=config.bootstrap_user)
    counts: dict[str, int] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        label, value = line.split("|", 1)
        counts[label] = int(value)
    return counts


def _extensions(config: PostgresConfig, database: str) -> set[str]:
    raw = psql(config, database, "SELECT extname FROM pg_extension", user=config.bootstrap_user)
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _restore(config: PostgresConfig, database: str, backup: Path, report: list[dict[str, object]]) -> None:
    started = time.monotonic()
    print(f"[restore] restaurando {backup.name} em {database}...")
    try:
        run_with_stdin_file(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                config.bootstrap_user,
                "-d",
                database,
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
            ],
            backup,
        )
    except Exception as exc:
        report.append(
            {
                "step": "pg_restore",
                "status": "failed",
                "seconds": round(time.monotonic() - started, 2),
            }
        )
        raise OpsError(f"pg_restore falhou: {exc}") from exc
    elapsed = round(time.monotonic() - started, 2)
    report.append({"step": "pg_restore", "status": "ok", "seconds": elapsed})
    print(f"[restore] pg_restore: ok ({elapsed}s)")


def _run(args: argparse.Namespace) -> dict[str, object]:
    config = PostgresConfig.from_environment()
    directory = args.dir.expanduser().resolve()
    backup = args.backup.expanduser().resolve() if args.backup else _latest_backup(directory)
    size = validate_backup_file(backup)

    report: list[dict[str, object]] = []
    scratch: str | None = None
    created = False
    started = time.monotonic()
    dev_before = _counts(config, config.database)
    result: dict[str, object] = {
        "drill": "restore",
        "database": config.database,
        "backup": str(backup),
        "backup_bytes": size,
        "started_at": utc_now().isoformat(),
        "dev_counts_before": dev_before,
    }
    try:
        scratch = create_scratch_database(config, "restore")
        created = True
        print(f"[restore] banco descartavel: {scratch}")
        _restore(config, scratch, backup, report)

        migration_started = time.monotonic()
        # O dump pode ter sido tirado antes de uma migration nova; atualizar o
        # banco restaurado ate head prova que o backup e recuperavel e que as
        # migrations pendentes aplicam sobre ele.
        alembic(config, scratch, ["upgrade", "head"], role="bootstrap")
        current = alembic(config, scratch, ["current"], role="bootstrap")
        check = alembic(config, scratch, ["check"], role="bootstrap")
        elapsed = round(time.monotonic() - migration_started, 2)
        report.append({"step": "alembic upgrade/current/check", "status": "ok", "seconds": elapsed})
        current_output = (current.stdout + current.stderr).decode("utf-8", errors="replace")
        check_output = (check.stdout + check.stderr).decode("utf-8", errors="replace")
        if "No new upgrade operations detected" not in check_output:
            raise OpsError(f"alembic check falhou no banco restaurado: {check_output[-500:]}")
        if "(head)" not in current_output:
            raise OpsError(f"alembic current nao apontou head: {current_output[-300:]}")
        print(f"[restore] alembic upgrade/current/check: ok ({elapsed}s)")

        counts = _counts(config, scratch)
        extensions = _extensions(config, scratch)
        missing = sorted(_REQUIRED_EXTENSIONS - extensions)
        if missing:
            raise OpsError(f"extensoes ausentes no banco restaurado: {missing}")
        if counts.get("products", 0) <= 0:
            raise OpsError("nenhum produto restaurado")
        print(f"[restore] contagens: {counts}")
        print(f"[restore] extensoes: {sorted(extensions & _REQUIRED_EXTENSIONS)}")

        dev_after = _counts(config, config.database)
        if dev_after != dev_before:
            raise OpsError(
                "o banco operacional mudou durante o drill: "
                f"{dev_before} -> {dev_after}"
            )
        print("[restore] banco operacional inalterado")

        result.update(
            {
                "status": "ok",
                "scratch_database": scratch,
                "restored_counts": counts,
                "extensions": sorted(extensions),
                "dev_counts_after": dev_after,
                "dev_unchanged": True,
                "restore_seconds": next(
                    float(step["seconds"]) for step in report if step["step"] == "pg_restore"
                ),
                "steps": report,
            }
        )
        return result
    except Exception as exc:
        result.update({"status": "failed", "error": str(exc), "steps": report})
        raise
    finally:
        if created and scratch is not None:
            if args.keep:
                print(f"[restore] --keep: banco descartavel preservado: {scratch}")
                result["scratch_database_preserved"] = scratch
            else:
                try:
                    drop_scratch_database(config, scratch, created=True)
                    print(f"[restore] banco descartavel removido: {scratch}")
                except Exception as exc:  # noqa: BLE001 - limpeza best effort com aviso
                    print(f"[restore] AVISO: falha ao remover {scratch}: {exc}", file=sys.stderr)
        result["total_seconds"] = round(time.monotonic() - started, 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drill de restauracao (banco descartavel).")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("BACKUP_DIR", str(REPO_ROOT / "backups"))),
        help="Diretorio que contem os backups.",
    )
    parser.add_argument("--backup", type=Path, default=None, help="Arquivo especifico (default: ultimo).")
    parser.add_argument("--keep", action="store_true", help="Preserva o banco descartavel para inspecao.")
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio final em JSON.")
    args = parser.parse_args(argv)
    try:
        result = _run(args)
    except Exception as exc:  # noqa: BLE001 - saida final e exit code
        if args.json:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"RELATORIO: FALHOU: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"RELATORIO: OK em {result['total_seconds']}s")
        print(f"  backup: {result['backup']} ({result['backup_bytes']} bytes)")
        print(f"  restauracao: {result['restore_seconds']}s")
        print(f"  contagens: {result['restored_counts']}")
        print(f"  banco operacional inalterado: {result['dev_unchanged']}")
        print(f"  banco descartavel removido: {'nao' if args.keep else 'sim'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
