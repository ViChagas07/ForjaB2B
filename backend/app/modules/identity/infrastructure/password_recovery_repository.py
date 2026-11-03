"""Persistencia do reset de senha por e-mail (tenant/RLS).

O fluxo nao autenticado resolve user_id/company_id a partir do reset_token
(Redis) e abre o UnitOfWork com esse tenant. O UPDATE em ``users`` e a
auditoria acontecem na mesma transacao; nenhuma PII entra no audit.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.ports import PasswordResetUser
from app.modules.identity.domain.enums import UserStatus

_GET_USER = text(
    "SELECT id, company_id, email, status, password_hash FROM users "
    "WHERE id = :user_id AND company_id = :company_id"
)
_LOCK_USER = text(
    "SELECT id, company_id, email, status, password_hash FROM users "
    "WHERE id = :user_id AND company_id = :company_id FOR UPDATE"
)
_UPDATE_PASSWORD = text(
    "UPDATE users SET password_hash = :password_hash, updated_at = now() "
    "WHERE id = :user_id AND company_id = :company_id"
)
_UPSERT_CREDENTIAL_EPOCH = text(
    "INSERT INTO user_credential_state "
    "(user_id, company_id, credential_epoch, password_changed_at, updated_at) "
    "VALUES (:user_id, :company_id, 1, now(), now()) "
    "ON CONFLICT (user_id) DO UPDATE SET "
    "credential_epoch = user_credential_state.credential_epoch + 1, "
    "password_changed_at = now(), updated_at = now() "
    "RETURNING credential_epoch"
)
_INSERT_AUDIT = text(
    "INSERT INTO audit_log "
    "(company_id, actor_user_id, action, resource, resource_id, details) "
    "VALUES (:company_id, :actor_user_id, :action, :resource, :resource_id, :details)"
)


def _to_user(mapping: Mapping[str, Any] | RowMapping) -> PasswordResetUser:
    status = UserStatus(str(mapping["status"]))
    return PasswordResetUser(
        user_id=mapping["id"],
        company_id=mapping["company_id"],
        email=str(mapping["email"]),
        password_hash=mapping["password_hash"],
        status=status,
    )


class SqlAlchemyPasswordResetRepository:
    """Implementacao da porta PasswordResetRepository sobre UoW/RLS."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_user(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PasswordResetUser | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                (
                    await uow.session.execute(
                        _GET_USER, {"user_id": user_id, "company_id": company_id}
                    )
                )
                .mappings()
                .first()
            )
            await uow.commit()
        return _to_user(row) if row is not None else None

    async def update_password_and_audit(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        password_hash: str,
        audit_action: str,
        audit_details: dict[str, str],
    ) -> int | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                (
                    await uow.session.execute(
                        _LOCK_USER, {"user_id": user_id, "company_id": company_id}
                    )
                )
                .mappings()
                .first()
            )
            user = _to_user(row) if row is not None else None
            if user is None or user.status is not UserStatus.ACTIVE:
                return None
            await uow.session.execute(
                _UPDATE_PASSWORD,
                {"password_hash": password_hash, "user_id": user_id, "company_id": company_id},
            )
            epoch_row = (
                await uow.session.execute(
                    _UPSERT_CREDENTIAL_EPOCH,
                    {"user_id": user_id, "company_id": company_id},
                )
            ).first()
            await uow.session.execute(
                _INSERT_AUDIT,
                {
                    "company_id": company_id,
                    "actor_user_id": user_id,
                    "action": audit_action,
                    "resource": "user",
                    "resource_id": user_id,
                    "details": json.dumps(audit_details),
                },
            )
            await uow.commit()
        if epoch_row is None:
            return None
        try:
            return max(1, int(epoch_row[0]))
        except (TypeError, ValueError):
            return None

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
