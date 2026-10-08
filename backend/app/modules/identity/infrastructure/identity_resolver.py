"""Resolucao de identidade por email via funcao SECURITY DEFINER.

Chama ``app.resolve_user_by_email`` (owner ``forja_auth``) SEM contexto de
tenant. Essa e a unica via pela qual a aplicacao le ``users`` antes de conhecer
o tenant: a tabela tem FORCE RLS e a policy padrao exige o company_id. A funcao
retorna apenas (user_id, company_id, status, password_hash) de um unico email.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.application.ports import ResolvedIdentity
from app.modules.identity.domain.enums import UserStatus

_RESOLVE_SQL = text(
    "SELECT user_id, company_id, status, password_hash FROM app.resolve_user_by_email(:email)"
)


class SqlAlchemyUserIdentityResolver:
    """Implementacao da porta UserIdentityResolver sobre a funcao SQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_by_email(self, email: str) -> ResolvedIdentity | None:
        async with self._session_factory() as session:
            result = await session.execute(_RESOLVE_SQL, {"email": email})
            row = result.mappings().first()
            if row is None:
                return None
            user_id: uuid.UUID = row["user_id"]
            company_id: uuid.UUID = row["company_id"]
            status = UserStatus(row["status"])
            password_hash: str | None = row["password_hash"]
            return ResolvedIdentity(
                user_id=user_id,
                company_id=company_id,
                status=status,
                password_hash=password_hash,
            )
