"""Repositorio SQLAlchemy do contexto de privacidade (LGPD).

Operacoes tenant-scoped via RLS. A anonimizacao e retificacao escrevem a
auditoria na MESMA transacao; a exclusao preserva FKs, registros financeiros,
fiscais e de auditoria (so anonimiza os campos identificadores do titular).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.privacy.application.ports import (
    AuditEntryView,
    ConsentView,
    PersonalDataView,
)
from app.modules.privacy.domain.enums import ConsentAction, ConsentPurpose
from app.modules.privacy.domain.privacy import anonymized_email, anonymized_name

_GET_USER = text(
    "SELECT id, company_id, email, full_name, phone, status, email_verified_at, last_login_at "
    "FROM users WHERE id = :user_id AND company_id = :company_id"
)
_GET_ROLE = text(
    "SELECT role FROM company_members WHERE user_id = :user_id AND company_id = :company_id "
    "ORDER BY created_at LIMIT 1"
)
_GET_CONSENTS = text(
    "SELECT DISTINCT ON (purpose) purpose, action, version, consented_at "
    "FROM consent_records WHERE user_id = :user_id AND company_id = :company_id "
    "ORDER BY purpose, consented_at DESC, id DESC"
)
_GET_AUDIT = text(
    "SELECT action, resource, resource_id, created_at FROM audit_log "
    "WHERE actor_user_id = :user_id AND company_id = :company_id "
    "ORDER BY created_at DESC, id DESC"
)
_UPDATE_RECTIFY = text(
    "UPDATE users SET full_name = :full_name, phone = :phone, updated_at = now() "
    "WHERE id = :user_id AND company_id = :company_id"
)
_UPDATE_ANONYMIZE = text(
    "UPDATE users SET email = :email, full_name = :full_name, phone = NULL, "
    "cpf_encrypted = NULL, status = 'SUSPENDED', updated_at = now() "
    "WHERE id = :user_id AND company_id = :company_id"
)
_INSERT_AUDIT = text(
    "INSERT INTO audit_log (company_id, actor_user_id, action, resource, resource_id, details) "
    "VALUES (:company_id, :actor_user_id, :action, :resource, :resource_id, :details)"
)
_INSERT_CONSENT = text(
    "INSERT INTO consent_records (company_id, user_id, purpose, action, version, document_hash) "
    "VALUES (:company_id, :user_id, :purpose, :action, :version, :document_hash)"
)


def _to_consent(row: Any) -> ConsentView:
    return ConsentView(
        purpose=row.purpose, action=row.action, version=row.version, consented_at=row.consented_at
    )


def _to_audit(row: Any) -> AuditEntryView:
    return AuditEntryView(
        action=row.action,
        resource=row.resource,
        resource_id=row.resource_id,
        created_at=row.created_at,
    )


class SqlAlchemyPrivacyRepository:
    """Implementacao da porta PrivacyRepository sobre UoW + SQL bruto."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_personal_data(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PersonalDataView | None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            user = (
                await uow.session.execute(_GET_USER, {"user_id": user_id, "company_id": company_id})
            ).first()
            if user is None:
                await uow.commit()
                return None
            role = (
                await uow.session.execute(_GET_ROLE, {"user_id": user_id, "company_id": company_id})
            ).first()
            consents = (
                await uow.session.execute(
                    _GET_CONSENTS, {"user_id": user_id, "company_id": company_id}
                )
            ).all()
            audit = (
                await uow.session.execute(
                    _GET_AUDIT, {"user_id": user_id, "company_id": company_id}
                )
            ).all()
            await uow.commit()

        return PersonalDataView(
            user_id=user.id,
            company_id=user.company_id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            status=user.status,
            role=role.role if role is not None else None,
            email_verified_at=user.email_verified_at,
            last_login_at=user.last_login_at,
            consents=[_to_consent(r) for r in consents],
            audit_entries=[_to_audit(r) for r in audit],
        )

    async def rectify(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        full_name: str,
        phone: str | None,
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _UPDATE_RECTIFY,
                {
                    "user_id": user_id,
                    "company_id": company_id,
                    "full_name": full_name,
                    "phone": phone,
                },
            )
            await uow.session.execute(
                _INSERT_AUDIT,
                {
                    "company_id": company_id,
                    "actor_user_id": user_id,
                    "action": "personal_data.rectify",
                    "resource": "user",
                    "resource_id": user_id,
                    "details": json.dumps({"scope": "full_name, phone"}),
                },
            )
            await uow.commit()

    async def anonymize(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _UPDATE_ANONYMIZE,
                {
                    "user_id": user_id,
                    "company_id": company_id,
                    "email": anonymized_email(user_id),
                    "full_name": anonymized_name(),
                },
            )
            await uow.session.execute(
                _INSERT_AUDIT,
                {
                    "company_id": company_id,
                    "actor_user_id": user_id,
                    "action": "personal_data.delete",
                    "resource": "user",
                    "resource_id": user_id,
                    "details": json.dumps({"scope": "anonymization"}),
                },
            )
            await uow.commit()

    async def record_consent(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        purpose: ConsentPurpose,
        action: ConsentAction,
        version: str,
        document_hash: str,
    ) -> None:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                _INSERT_CONSENT,
                {
                    "company_id": company_id,
                    "user_id": user_id,
                    "purpose": purpose.value,
                    "action": action.value,
                    "version": version,
                    "document_hash": document_hash,
                },
            )
            await uow.commit()

    async def get_current_consents(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ConsentView]:
        tenant = TenantContext(company_id=company_id)
        async with self._uow_factory.begin(tenant) as uow:
            rows = (
                await uow.session.execute(
                    _GET_CONSENTS, {"user_id": user_id, "company_id": company_id}
                )
            ).all()
            await uow.commit()
            return [_to_consent(r) for r in rows]
