"""Ambiente de migrations do Alembic.

Fronteira bootstrap vs. aplicacao:
- O que NAO entra aqui: roles, usuarios PostgreSQL, extensoes, schema `app`,
  funcoes `app.*` (current_company_id, current_user_id, set_tenant_context)
  e qualquer DDL de docker/postgres (executada uma unica vez no initdb).
- O que entra aqui (a partir da Fase 1): tabelas de dominio, indexes e
  policies RLS das tabelas de dominio, geradas/evoluidas por revision.

Credencial: migrations exigem DDL, entao usam EXCLUSIVAMENTE a role
administrativa restrita (forja_admin) via DATABASE_ADMIN_URL. A role de
runtime (forja_app, DATABASE_URL) nao tem CREATE e falharia, por desenho.
DATABASE_ADMIN_URL nunca e injetada nos containers de runtime; quem executa
e o operador/CI (ver Makefile, alvo `migrate`).

`include_object` bloqueia qualquer objeto do schema `app`, mesmo que um
autogenerate futuro tente tocar a fundacao RLS.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Registrar todos os mapeadores ORM para que Base.metadata reflita o schema
# de dominio (target_metadata abaixo). Sem este import, o autogenerate/check
# nao enxergaria as tabelas da Fase 1.
import app.infrastructure.db.models  # noqa: F401
from alembic import context
from app.core.config import normalize_async_database_url
from app.infrastructure.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


class MigrationCredentialError(RuntimeError):
    """Credencial administrativa ausente para executar migrations."""


def _migration_url() -> str:
    url = os.environ.get("DATABASE_ADMIN_URL")
    if url:
        return normalize_async_database_url(url)
    raise MigrationCredentialError(
        "DATABASE_ADMIN_URL ausente: migrations exigem a role administrativa "
        "restrita (forja_admin). O runtime (DATABASE_URL, forja_app) nao "
        "executa DDL. Ver Makefile, alvo `migrate`."
    )


def _migration_connect_args() -> dict[str, object]:
    """Permite trocar para a role owner via membership (Render gerenciado).

    Em alguns bancos gerenciados a unica credencial disponivel e a role
    principal. Se ela for membro de ``forja_admin`` com SET, a conexao pode
    iniciar ja como owner usando ``DATABASE_ADMIN_ROLE=forja_admin``.
    """
    role = os.environ.get("DATABASE_ADMIN_ROLE", "").strip()
    if not role:
        return {}
    return {"server_settings": {"role": role}}


# Objetos derivados da busca (Fases 4/5) criados por migration com SQL puro
# (nao modelados no ORM de proposito): tabela de embeddings + indices trigram/FTS
# + indice HNSW. Ficam fora do autogenerate/`alembic check` para nao gerar drift
# falso nem exigir um tipo `vector` no metadata.
_SEARCH_MANAGED_OBJECTS = frozenset(
    {
        "product_embeddings",
        "ix_products_search_text",
        "ix_products_sku_trgm",
        "ix_products_name_trgm",
        "ix_product_embeddings_hnsw",
    }
)


def include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object,
) -> bool:
    """Exclui o schema `app` (bootstrap) e os objetos derivados da busca."""
    schema = getattr(obj, "schema", None)
    is_search_managed = name is not None and name in _SEARCH_MANAGED_OBJECTS
    return schema != "app" and not is_search_managed


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_online(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(
        _migration_url(), connect_args=_migration_connect_args()
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations_online)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
