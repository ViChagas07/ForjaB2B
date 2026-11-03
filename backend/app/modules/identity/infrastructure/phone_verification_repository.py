"""Persistencia/auditoria da verificacao de telefone com RLS.

O claim usa a funcao SECURITY DEFINER `public.claim_verified_phone` (migration
0044), que serializa a corrida por telefone e troca o vinculo anterior na
mesma transacao. A leitura do e-mail do dono antigo e feita com o tenant dele,
nunca com bypass de RLS.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.errors import PhoneVerificationConflictError
from app.modules.identity.application.ports import PreviousPhoneOwner

_SELECT_PHONE = text(
    "SELECT phone_e164 FROM user_verified_phones "
    "WHERE company_id = :company_id AND user_id = :user_id"
)
_CLAIM_PHONE = text(
    "SELECT previous_user_id, previous_company_id "
    "FROM public.claim_verified_phone(:phone, :user_id, :company_id)"
)
_SELECT_EMAIL = text("SELECT email FROM users WHERE company_id = :company_id AND id = :user_id")
_INSERT_AUDIT = text(
    "INSERT INTO audit_log "
    "(company_id, actor_user_id, action, resource, resource_id, details) "
    "VALUES (:company_id, :actor_user_id, :action, :resource, :resource_id, :details)"
)


class SqlAlchemyPhoneVerificationRepository:
    """Implementacao da porta PhoneVerificationRepository sobre UoW/RLS."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_verified_phone(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_PHONE, {"company_id": company_id, "user_id": user_id}
                )
            ).first()
            await uow.commit()
        return None if row is None else str(row[0])

    async def claim_verified_phone(
        self, *, phone_e164: str, user_id: uuid.UUID, company_id: uuid.UUID
    ) -> PreviousPhoneOwner | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        try:
            async with self._uow_factory.begin(tenant) as uow:
                row = (
                    await uow.session.execute(
                        _CLAIM_PHONE,
                        {
                            "phone": phone_e164,
                            "user_id": user_id,
                            "company_id": company_id,
                        },
                    )
                ).first()
                await uow.commit()
        except IntegrityError as exc:
            raise PhoneVerificationConflictError() from exc
        if row is None or row[0] is None:
            return None
        return PreviousPhoneOwner(user_id=row[0], company_id=row[1])

    async def get_user_email(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    _SELECT_EMAIL, {"company_id": company_id, "user_id": user_id}
                )
            ).first()
            await uow.commit()
        return None if row is None else str(row[0])

    async def record_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        details: dict[str, str],
    ) -> None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _INSERT_AUDIT,
                {
                    "company_id": company_id,
                    "actor_user_id": user_id,
                    "action": action,
                    "resource": "user",
                    "resource_id": user_id,
                    "details": json.dumps(details),
                },
            )
            await uow.commit()
