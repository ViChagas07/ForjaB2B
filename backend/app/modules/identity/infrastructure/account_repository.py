"""Persistencia do perfil da conta sobre users + consumer_profiles."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import String, Uuid, column, select, table
from sqlalchemy.orm import selectinload

from app.application.ports.tenant import TenantContext
from app.domain.consumer import Gender
from app.domain.currency import normalize_currency
from app.infrastructure.db.models.identity import ConsumerProfile, User
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.ports import AccountRecord

# Tabela leve (sem importar o modulo companies) apenas para ler account_type.
_COMPANIES = table(
    "companies",
    column("id", Uuid),
    column("account_type", String(24)),
)


class SqlAlchemyAccountRepository:
    def __init__(self, uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def get(self, company_id: uuid.UUID, user_id: uuid.UUID) -> AccountRecord | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    select(User, ConsumerProfile, _COMPANIES.c.account_type)
                    .outerjoin(ConsumerProfile, ConsumerProfile.user_id == User.id)
                    .join(_COMPANIES, _COMPANIES.c.id == User.company_id)
                    .where(User.id == user_id, User.company_id == company_id)
                )
            ).first()
            await uow.commit()
        if row is None:
            return None
        user, profile, account_type = row
        return _record(user, profile, account_type)

    async def update(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        full_name: str,
        phone: str | None,
        birth_date: date | None,
        gender: Gender | None,
        postal_code: str | None,
    ) -> AccountRecord | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    select(User, ConsumerProfile, _COMPANIES.c.account_type)
                    .outerjoin(ConsumerProfile, ConsumerProfile.user_id == User.id)
                    .join(_COMPANIES, _COMPANIES.c.id == User.company_id)
                    .options(selectinload(User.consumer_profile))
                    .where(User.id == user_id, User.company_id == company_id)
                )
            ).first()
            if row is None:
                await uow.commit()
                return None
            user, profile, account_type = row
            if profile is not None:
                # Contas PERSON mantem as colunas antigas preenchidas; o
                # formulario nao consegue apagar dados obrigatorios.
                birth_date = birth_date or profile.birth_date
                gender = gender or profile.gender
                postal_code = postal_code or profile.postal_code
                profile.birth_date = birth_date
                profile.gender = gender
                profile.postal_code = postal_code
            user.full_name = full_name
            user.phone = phone
            user.birth_date = birth_date
            user.gender = gender
            user.postal_code = postal_code
            await uow.commit()
        return _record(user, profile, account_type)

    async def update_display_currency(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        display_currency: str,
    ) -> AccountRecord | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    select(User, ConsumerProfile, _COMPANIES.c.account_type)
                    .outerjoin(ConsumerProfile, ConsumerProfile.user_id == User.id)
                    .join(_COMPANIES, _COMPANIES.c.id == User.company_id)
                    .where(User.id == user_id, User.company_id == company_id)
                )
            ).first()
            if row is None:
                await uow.commit()
                return None
            user, profile, account_type = row
            user.display_currency = normalize_currency(display_currency)
            await uow.commit()
        return _record(user, profile, account_type)


def _record(user: User, profile: ConsumerProfile | None, account_type: object) -> AccountRecord:
    return AccountRecord(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        birth_date=user.birth_date or (profile.birth_date if profile is not None else None),
        gender=user.gender or (profile.gender if profile is not None else None),
        postal_code=user.postal_code or (profile.postal_code if profile is not None else None),
        display_currency=normalize_currency(user.display_currency),
        account_type=str(account_type),
    )
