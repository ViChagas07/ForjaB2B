#!/usr/bin/env python3
"""Drill de rollback de migrations do Forja B2B.

Fluxo (sempre em um banco descartavel ``forja_scratch_*``):

1. cria o banco descartavel e replica o bootstrap real (extensoes, schema app);
2. ``alembic upgrade head``;
3. aplica o seed de demonstracao e registra contagens/checksums;
4. ``alembic downgrade base`` (ou ``-N`` com ``--steps``);
5. ``alembic upgrade head`` novamente;
6. reaplica o seed (idempotente) e compara contagens/checksums;
7. ``alembic check`` e confere a revisao atual.

O banco operacional nunca e alvo: o script cria, usa e remove apenas o banco que
ele mesmo criou. Qualquer falha retorna codigo != 0.

Uso:
    python scripts/migration_drill.py [--steps N] [--keep] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable

from ops_common import (
    OpsError,
    PostgresConfig,
    alembic,
    bootstrap_scratch_database,
    create_scratch_database,
    drop_scratch_database,
    psql,
    seed,
    utc_now,
)

_SNAPSHOT_SQL = """
SELECT 'products|' || count(*) || '|' ||
       coalesce(md5(string_agg(sku || ':' || base_unit_price::text, ',' ORDER BY sku)), 'empty')
FROM products
UNION ALL
SELECT 'companies|' || count(*) || '|' ||
       coalesce(md5(string_agg(cnpj || ':' || legal_name, ',' ORDER BY cnpj)), 'empty')
FROM companies
UNION ALL
SELECT 'users|' || count(*) || '|' ||
       coalesce(md5(string_agg(email, ',' ORDER BY email)), 'empty')
FROM users
UNION ALL
SELECT 'price_rules|' || count(*) || '|' ||
       coalesce(md5(string_agg(
           company_id::text || ':' || rule_type || ':' ||
           coalesce(product_id::text, '-') || ':' ||
           coalesce(category_id::text, '-') || ':' ||
           coalesce(percent::text, '-') || ':' ||
           coalesce(unit_price::text, '-'),
           ',' ORDER BY company_id, rule_type, product_id, category_id
       )), 'empty')
FROM company_price_rules
UNION ALL
SELECT 'translations|' || count(*) || '|' ||
       coalesce(md5(string_agg(
           product_id::text || ':' || locale || ':' || coalesce(name, ''),
           ',' ORDER BY product_id, locale
       )), 'empty')
FROM product_translations
"""


def _snapshot(config: PostgresConfig, database: str) -> dict[str, str]:
    # Superusuario de bootstrap: as tabelas de tenant tem FORCE RLS e a role
    # administrativa sem contexto de tenant veria zero linhas.
    raw = psql(config, database, _SNAPSHOT_SQL, user=config.bootstrap_user)
    snapshot: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        label, count, digest = line.split("|", 2)
        snapshot[label] = f"{count}|{digest}"
    expected = {"products", "companies", "users", "price_rules", "translations"}
    if set(snapshot) != expected:
        raise OpsError(f"snapshot incompleto: {sorted(snapshot)}")
    return snapshot


def _timed[T](label: str, action: Callable[[], T], report: list[dict[str, object]]) -> T:
    started = time.monotonic()
    print(f"[drill] {label}...")
    try:
        result = action()
    except Exception as exc:
        elapsed = round(time.monotonic() - started, 2)
        report.append({"step": label, "status": "failed", "seconds": elapsed})
        raise OpsError(f"{label}: {exc}") from exc
    elapsed = round(time.monotonic() - started, 2)
    report.append({"step": label, "status": "ok", "seconds": elapsed})
    print(f"[drill] {label}: ok ({elapsed}s)")
    return result


def _head_revision(config: PostgresConfig, database: str) -> str:
    completed = alembic(config, database, ["heads"])
    lines = [line.strip() for line in completed.stdout.decode().splitlines() if line.strip()]
    if not lines:
        raise OpsError("alembic heads nao retornou revisao")
    return lines[0].split()[0]


def _current_revision(config: PostgresConfig, database: str) -> str:
    sql = (
        "SELECT CASE WHEN to_regclass('public.alembic_version') IS NULL THEN '' "
        "ELSE (SELECT version_num FROM alembic_version) END"
    )
    return psql(config, database, sql)


def _downgrade_target(config: PostgresConfig, database: str, steps: int) -> None:
    if steps > 0:
        alembic(config, database, ["downgrade", f"-{steps}"])
        return
    alembic(config, database, ["downgrade", "base"])


def _run(args: argparse.Namespace) -> dict[str, object]:  # noqa: C901 - orquestracao linear
    config = PostgresConfig.from_environment()
    report: list[dict[str, object]] = []
    scratch: str | None = None
    created = False
    result: dict[str, object] = {
        "drill": "migration",
        "database": config.database,
        "started_at": utc_now().isoformat(),
    }
    try:
        scratch = _timed(
            "criar banco descartavel",
            lambda: create_scratch_database(config, "migration"),
            report,
        )
        created = True
        print(f"[drill] banco descartavel: {scratch}")

        _timed(
            "bootstrap do banco descartavel",
            lambda: bootstrap_scratch_database(config, scratch),
            report,
        )
        _timed(
            "upgrade head (inicial)", lambda: alembic(config, scratch, ["upgrade", "head"]), report
        )
        _timed("seed inicial", lambda: seed(config, scratch), report)
        before = _timed("snapshot do seed (antes)", lambda: _snapshot(config, scratch), report)
        print(f"[drill] seed antes: {before}")

        _timed(
            f"downgrade {'-N' if args.steps else 'base'}",
            lambda: _downgrade_target(config, scratch, args.steps),
            report,
        )
        version_after_downgrade = _current_revision(config, scratch)
        if args.steps <= 0:
            if version_after_downgrade:
                raise OpsError(f"downgrade base deixou alembic_version={version_after_downgrade!r}")
            products = psql(config, scratch, "SELECT to_regclass('public.products') IS NULL")
            if products != "t":
                raise OpsError("downgrade base nao removeu a tabela products")
        print(f"[drill] revisao apos downgrade: {version_after_downgrade or '<base>'}")

        _timed(
            "upgrade head (final)", lambda: alembic(config, scratch, ["upgrade", "head"]), report
        )
        _timed("seed final (idempotente)", lambda: seed(config, scratch), report)
        after = _timed("snapshot do seed (depois)", lambda: _snapshot(config, scratch), report)
        print(f"[drill] seed depois: {after}")
        if before != after:
            raise OpsError(f"integridade do seed divergiu apos o ciclo: {before} != {after}")

        head = _head_revision(config, scratch)
        current = _current_revision(config, scratch)
        if current != head:
            raise OpsError(f"revisao atual {current!r} difere do head {head!r}")

        check = _timed("alembic check", lambda: alembic(config, scratch, ["check"]), report)
        check_output = (check.stdout + check.stderr).decode("utf-8", errors="replace").strip()
        if "No new upgrade operations detected" not in check_output:
            raise OpsError(f"alembic check nao confirmou o esquema: {check_output[-500:]}")

        result.update(
            {
                "status": "ok",
                "scratch_database": scratch,
                "head_revision": head,
                "seed_snapshot": after,
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
                print(f"[drill] --keep: banco descartavel preservado: {scratch}")
                result["scratch_database_preserved"] = scratch
            else:
                try:
                    drop_scratch_database(config, scratch, created=True)
                    print(f"[drill] banco descartavel removido: {scratch}")
                except Exception as exc:  # noqa: BLE001 - limpeza best effort com aviso
                    print(f"[drill] AVISO: falha ao remover {scratch}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Drill de rollback de migrations (banco descartavel)."
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=0,
        help="Numero de revisoes a reverter (0 = ate a base).",
    )
    parser.add_argument(
        "--keep", action="store_true", help="Preserva o banco descartavel para inspecao."
    )
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio final em JSON.")
    args = parser.parse_args(argv)
    if args.steps < 0:
        parser.error("--steps deve ser >= 0")
    started = time.monotonic()
    try:
        result = _run(args)
    except Exception as exc:  # noqa: BLE001 - saida final e exit code
        elapsed = round(time.monotonic() - started, 2)
        if args.json:
            print(
                json.dumps(
                    {"status": "failed", "error": str(exc), "seconds": elapsed}, ensure_ascii=False
                )
            )
        else:
            print(f"RELATORIO: FALHOU em {elapsed}s: {exc}", file=sys.stderr)
        return 1
    result["total_seconds"] = round(time.monotonic() - started, 2)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"RELATORIO: OK em {result['total_seconds']}s")
        for step in result["steps"]:  # type: ignore[union-attr]
            print(f"  - {step['step']}: {step['status']} ({step['seconds']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
