"""Leitura do vinculo usuario x empresa dentro do tenant autenticado.

A consulta roda na UoW com ``TenantContext(company_id, user_id)``: a RLS
garante o isolamento e a leitura de ``company_members``/``users`` da propria
empresa. Nao confia em company_id vindo do cliente.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.application.ports.tenant import TenantContext
from app.infrastructure.db.models.identity import CompanyMember, User
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.ports import Membership


class SqlAlchemyMembershipReader:
    """Implementacao da porta MembershipReader sobre ORM + UoW com tenant."""

    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get_membership(self, company_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            stmt = (
                select(CompanyMember, User)
                .join(User, User.id == CompanyMember.user_id)
                .where(
                    CompanyMember.company_id == company_id,
                    CompanyMember.user_id == user_id,
                )
            )
            row = (await uow.session.execute(stmt)).first()
            await uow.commit()
            if row is None:
                return None
            member, user = row
            return Membership(
                role=member.role,
                status=member.status,
                full_name=user.full_name,
                email=user.email,
            )
