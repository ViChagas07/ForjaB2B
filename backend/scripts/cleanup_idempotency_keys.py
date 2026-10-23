"""Remove chaves de idempotencia expiradas.

Uso (a partir de backend/):

    DATABASE_ADMIN_URL=postgresql+asyncpg://... python scripts/cleanup_idempotency_keys.py
    python scripts/cleanup_idempotency_keys.py --dry-run

A role administrativa (forja_admin) nao tem BYPASSRLS. Para o expurgo global,
a script desabilita FORCE RLS dentro da MESMA transacao (o runtime continua
sujeito a RLS) e restaura antes do commit. Em erro, o rollback desfaz tudo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if not (BACKEND_ROOT / "app").is_dir():  # container: script em /app/scripts
    BACKEND_ROOT = REPO_ROOT
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.metrics import increment_idempotency_keys_purged  # noqa: E402
from app.infrastructure.db.engine import create_engine  # noqa: E402

_COUNT = text("SELECT count(*) FROM idempotency_keys WHERE expires_at < :now")
_DELETE = text("DELETE FROM idempotency_keys WHERE expires_at < :now")


async def _run(*, dry_run: bool) -> dict[str, object]:
    settings = Settings()
    if not settings.database_admin_url:
        raise SystemExit("DATABASE_ADMIN_URL ausente: o expurgo global exige a role forja_admin.")
    engine = create_engine(settings, admin=True)
    now = datetime.now(UTC)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE idempotency_keys NO FORCE ROW LEVEL SECURITY"))
            total = int((await conn.execute(_COUNT, {"now": now})).scalar_one())
            deleted = 0
            if not dry_run and total > 0:
                result = await conn.execute(_DELETE, {"now": now})
                deleted = int(result.rowcount or 0)
            await conn.execute(text("ALTER TABLE idempotency_keys FORCE ROW LEVEL SECURITY"))
    finally:
        await engine.dispose()

    if not dry_run:
        increment_idempotency_keys_purged(deleted)
    return {
        "dry_run": dry_run,
        "cutoff": now.isoformat(),
        "expired": total,
        "deleted": deleted,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Limpa chaves de idempotencia expiradas.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas conta, sem apagar.")
    args = parser.parse_args(argv)
    report = asyncio.run(_run(dry_run=args.dry_run))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
