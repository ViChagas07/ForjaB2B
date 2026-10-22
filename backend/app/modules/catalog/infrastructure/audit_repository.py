"""Implementacao da porta de auditoria do catalogo (tenant-scoped).

A trilha ``audit_log`` tem RLS por ``company_id``. Por isso a escrita usa o
UoW de runtime com o contexto do tenant do ator (role ``forja_app`` + GUCs),
e nao o UoW administrativo (sem tenant) usado no catalogo global.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory


class SqlAlchemyAuditLogRepository:
    """Grava entradas em ``audit_log`` no contexto da empresa do ator."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def record(
        self,
        *,
        company_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        action: str,
        resource: str,
        resource_id: uuid.UUID,
        details: dict[str, object] | None = None,
    ) -> None:
        tenant = TenantContext(company_id=company_id, user_id=actor_user_id)
        async with self._uow_factory.begin(tenant) as uow:
            await uow.session.execute(
                text(
                    "INSERT INTO audit_log "
                    "(company_id, actor_user_id, action, resource, resource_id, details) "
                    "VALUES (:company_id, :actor_user_id, :action, :resource, "
                    ":resource_id, CAST(:details AS jsonb))"
                ),
                {
                    "company_id": company_id,
                    "actor_user_id": actor_user_id,
                    "action": action,
                    "resource": resource,
                    "resource_id": resource_id,
                    "details": json.dumps(details, ensure_ascii=False) if details else None,
                },
            )
            await uow.commit()
