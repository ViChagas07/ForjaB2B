"""Sondas leves de compatibilidade de schema.

O deploy pode acontecer antes de a migration ser aplicada (por exemplo, em
planos do Render sem pre-deploy). Em vez de deixar login/onboarding quebrarem
com 500, lemos ``information_schema`` (visivel para a role de runtime) e
ativamos um caminho legado seguro:

- sem ``companies.account_type``, contas existentes sao tratadas como
  ``COMPANY`` (o que tambem mantem o Google bloqueado para empresas);
- sem ``consumer_profiles``, o cadastro de consumidor responde 503 explicito
  em vez de estourar um erro interno.

As funcoes sao intencionalmente pequenas e sem cache: o schema pode mudar
entre o start e a primeira request, e a checagem custa apenas uma consulta ao
catalogo.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

_ACCOUNT_TYPE_EXISTS = text(
    "SELECT EXISTS ("
    "SELECT 1 FROM information_schema.columns "
    "WHERE table_schema = 'public' "
    "AND table_name = 'companies' "
    "AND column_name = 'account_type'"
    ")"
)
_CONSUMER_PROFILE_TABLE_EXISTS = text(
    "SELECT to_regclass('public.consumer_profiles') IS NOT NULL"
)
_CONSUMER_SCHEMA_CURRENT = text(
    "SELECT EXISTS ("
    "SELECT 1 FROM information_schema.columns "
    "WHERE table_schema = 'public' "
    "AND table_name = 'companies' "
    "AND column_name = 'account_type'"
    ") AND to_regclass('public.consumer_profiles') IS NOT NULL"
)


async def has_account_type(session: AsyncSession) -> bool:
    """Indica se a coluna ``companies.account_type`` ja existe."""
    return bool((await session.execute(_ACCOUNT_TYPE_EXISTS)).scalar_one())


async def has_consumer_profiles(session: AsyncSession) -> bool:
    """Indica se a tabela ``consumer_profiles`` ja existe."""
    return bool((await session.execute(_CONSUMER_PROFILE_TABLE_EXISTS)).scalar_one())


async def has_consumer_schema(session: AsyncSession) -> bool:
    """Indica se todas as estruturas do cadastro CPF estao presentes."""
    return bool((await session.execute(_CONSUMER_SCHEMA_CURRENT)).scalar_one())


async def schema_is_current(engine: AsyncEngine) -> bool:
    """Sonda usada pelo endpoint de diagnostico (/health/schema)."""
    async with engine.connect() as connection:
        return bool((await connection.execute(_CONSUMER_SCHEMA_CURRENT)).scalar_one())
