"""Persistencia do vinculo usuario x identidade externa (Google).

A tabela ``user_external_identities`` e tenant-scoped (RLS por company_id). O
vinculo e idempotente; a unicidade global ``(provider, subject)`` impede que a
mesma identidade Google seja vinculada a dois usuarios (account takeover).
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.errors import OAuthAccountLinkConflictError

_PROVIDER_SUBJECT_UNIQUE = "uq_user_external_identities_provider_subject"

_SELECT_BY_SUBJECT = text(
    "SELECT user_id FROM user_external_identities WHERE provider = :provider AND subject = :subject"
)
_INSERT_LINK = text(
    "INSERT INTO user_external_identities (user_id, company_id, provider, subject, email) "
    "VALUES (:user_id, :company_id, :provider, :subject, :email)"
)


def _constraint_name(exc: BaseException) -> str:
    current: BaseException | None = exc
    while current is not None:
        name = getattr(current, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        current = current.__cause__
    return ""


class SqlAlchemyExternalIdentityRepository:
    """Implementacao da porta ExternalIdentityRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def link(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        provider: str,
        subject: str,
        email: str,
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            existing = (
                await uow.session.execute(
                    _SELECT_BY_SUBJECT, {"provider": provider, "subject": subject}
                )
            ).first()
            if existing is not None:
                if existing.user_id != user_id:
                    raise OAuthAccountLinkConflictError()
                await uow.commit()
                return

            try:
                await uow.session.execute(
                    _INSERT_LINK,
                    {
                        "user_id": user_id,
                        "company_id": company_id,
                        "provider": provider,
                        "subject": subject,
                        "email": email,
                    },
                )
                await uow.commit()
            except Exception as exc:
                if _constraint_name(exc) == _PROVIDER_SUBJECT_UNIQUE:
                    raise OAuthAccountLinkConflictError() from exc
                raise
