"""Resolucao nao autenticada de usuario por telefone verificado.

Chama a funcao SECURITY DEFINER da 0043; o runtime nao le a tabela direto.
O status ACTIVE e conferido depois, no tenant resolvido.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.application.ports import VerifiedPhoneOwner

_RESOLVE = text("SELECT user_id, company_id FROM public.resolve_user_by_verified_phone(:phone)")


class SqlAlchemyVerifiedPhoneResolver:
    """Implementacao da porta VerifiedPhoneResolver sobre a funcao SQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve(self, *, phone_e164: str) -> VerifiedPhoneOwner | None:
        async with self._session_factory() as session:
            row = (await session.execute(_RESOLVE, {"phone": phone_e164})).mappings().first()
        if row is None:
            return None
        return VerifiedPhoneOwner(user_id=row["user_id"], company_id=row["company_id"])
