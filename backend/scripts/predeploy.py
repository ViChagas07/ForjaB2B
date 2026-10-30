"""Aplica as migrations do Alembic no pre-deploy do Render.

O Render executa este script com a imagem da NOVA versao, antes de liberar o
trafego. Se ``DATABASE_ADMIN_URL`` estiver ausente, se a credencial nao puder
executar DDL ou se o upgrade falhar, o script termina com codigo diferente de
zero e o Render aborta o deploy. Isso impede o cenario em que o codigo sobe
esperando colunas que o banco ainda nao possui.

Uso (a partir de ``backend/``):

    DATABASE_ADMIN_URL=postgresql://forja_admin:...@host/db?sslmode=require \
        python scripts/predeploy.py

A credencial deve ser a role de migracao (``forja_admin`` em producao), owner
das tabelas. A role de runtime (``forja_app``) nao tem privilegio de DDL. O
script nunca imprime a URL nem a senha.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import normalize_async_database_url  # noqa: E402

# Lock consultivo de sessao: impede que duas instancias iniciem o Alembic ao
# mesmo tempo em um deploy com mais de um worker/instancia. A chave e estavel e
# vive apenas no cluster do banco.
_MIGRATION_LOCK_KEY = 0x464F524A41

_PREFLIGHT_QUERY = text(
    """
    SELECT
        current_user AS role,
        to_regclass('public.products') IS NOT NULL AS has_products,
        COALESCE(
            (
                SELECT pg_has_role(current_user, c.relowner, 'USAGE')
                FROM pg_class c
                WHERE c.oid = to_regclass('public.products')
            ),
            true
        ) AS can_act_as_owner,
        has_schema_privilege(current_user, 'public', 'CREATE') AS can_create
    """
)


class PreDeployError(RuntimeError):
    """Falha de configuracao ou de pre-condicao do pre-deploy."""


def _admin_url() -> str:
    url = os.environ.get("DATABASE_ADMIN_URL", "").strip()
    if not url:
        raise PreDeployError(
            "DATABASE_ADMIN_URL ausente. Configure no servico do Render a URL da "
            "role de migracao (forja_admin), nunca a role de runtime (forja_app)."
        )
    runtime_url = os.environ.get("DATABASE_URL", "").strip()
    if runtime_url and url == runtime_url:
        raise PreDeployError(
            "DATABASE_ADMIN_URL aponta para a mesma URL de runtime (forja_app). "
            "Migrations exigem a role administrativa com DDL (forja_admin)."
        )
    return normalize_async_database_url(url)


async def _preflight(url: str) -> dict[str, object]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            row = (await connection.execute(_PREFLIGHT_QUERY)).mappings().one()
    finally:
        await engine.dispose()

    if row["has_products"] and not row["can_act_as_owner"]:
        raise PreDeployError(
            f"O usuario {row['role']!r} nao e owner das tabelas de schema. "
            "Use a role administrativa que criou o schema (forja_admin em "
            "producao); a role de bootstrap/app nao executa DDL."
        )
    if not row["can_create"]:
        raise PreDeployError(
            f"O usuario {row['role']!r} nao tem CREATE no schema public. "
            "Use a role administrativa de migrations."
        )
    return {"role": row["role"], "has_products": row["has_products"]}


async def _current_revision(url: str) -> str | None:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_connection: MigrationContext.configure(
                    sync_connection
                ).get_current_revision()
            )
    finally:
        await engine.dispose()


def _config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


async def _upgrade_with_lock(url: str) -> None:
    """Aplica o upgrade segurando um advisory lock entre processos."""
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_advisory_lock(:key)"),
                {"key": _MIGRATION_LOCK_KEY},
            )
            await connection.commit()
            try:
                await asyncio.to_thread(command.upgrade, _config(), "head")
            finally:
                with suppress(Exception):
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"),
                        {"key": _MIGRATION_LOCK_KEY},
                    )
                    await connection.commit()
    finally:
        await engine.dispose()


def main() -> int:
    url = _admin_url()
    head = ScriptDirectory.from_config(_config()).get_current_head()
    preflight = asyncio.run(_preflight(url))
    print(f"[predeploy] connected as {preflight['role']!r}; head={head}", flush=True)

    asyncio.run(_upgrade_with_lock(url))

    current = asyncio.run(_current_revision(url))
    if current != head:
        raise PreDeployError(
            f"Migration nao atingiu o head: banco em {current!r}, esperado {head!r}."
        )
    print(f"[predeploy] migrations at head: {current}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreDeployError as exc:
        print(f"[predeploy] ERRO: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2) from exc
