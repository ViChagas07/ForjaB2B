"""Persistencia do perfil da conta sobre users + consumer_profiles + user_preferences.

As preferencias do usuario (moeda, privacidade, avatar, whatsapp) sao
armazenadas na tabela `user_preferences` (Fase 2). As colunas antigas em
`users` foram removidas/marcadas como deferred para compatibilidade com
producao onde as migrations 0037-0040 nao foram aplicadas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid, column, select, table
from sqlalchemy.orm import selectinload

from app.application.ports.tenant import TenantContext
from app.domain.consumer import Gender
from app.domain.currency import normalize_currency
from app.infrastructure.db.models.identity import ConsumerProfile, User
from app.infrastructure.db.models.user_preferences import UserPreferences
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.modules.identity.application.avatar import account_avatar_url
from app.modules.identity.application.ports import AccountRecord, AvatarBlob

if TYPE_CHECKING:
    from app.infrastructure.db.models.identity import User

# Tabela leve (sem importar o modulo companies) apenas para ler account_type.
_COMPANIES = table(
    "companies",
    column("id", Uuid),
    column("account_type", String(24)),
)


async def _get_preferences_or_create(uow, company_id: uuid.UUID, user_id: uuid.UUID) -> UserPreferences:
    """Obtem ou cria as preferencias do usuario (upsert)."""
    prefs = await uow.session.get(UserPreferences, user_id)
    if prefs is None:
        prefs = UserPreferences(user_id=user_id, company_id=company_id)
        uow.session.add(prefs)
    return prefs


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
                    .options(
                        selectinload(User.preferences),
                        selectinload(User.consumer_profile),
                    )
                    .where(User.id == user_id, User.company_id == company_id)
                )
            ).first()
            await uow.commit()
        if row is None:
            return None
        user, profile, account_type = row
        prefs = user.preferences
        return _record(user, profile, account_type, prefs)

    async def update(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        full_name: str,
        phone: str | None,
        birth_date: date | None = None,
        gender: Gender | None = None,
        postal_code: str | None = None,
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
            user.full_name = full_name
            user.phone = phone

            # Atualiza consumer_profiles se informado (contas PERSON)
            if birth_date is not None or gender is not None or postal_code is not None:
                if profile is None:
                    profile = ConsumerProfile(user_id=user_id, company_id=company_id)
                    uow.session.add(profile)
                if birth_date is not None:
                    profile.birth_date = birth_date
                if gender is not None:
                    profile.gender = gender
                if postal_code is not None:
                    profile.postal_code = postal_code

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
                    .options(selectinload(User.preferences))
                    .where(User.id == user_id, User.company_id == company_id)
                )
            ).first()
            if row is None:
                await uow.commit()
                return None
            user, profile, account_type = row
            prefs = user.preferences
            if prefs is None:
                prefs = UserPreferences(user_id=user_id, company_id=company_id)
                uow.session.add(prefs)
            prefs.display_currency = normalize_currency(display_currency)
            await uow.commit()
        return _record(user, profile, account_type, prefs)

    async def update_hide_spending(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        hide_spending: bool,
    ) -> AccountRecord | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            row = (
                await uow.session.execute(
                    select(User, ConsumerProfile, _COMPANIES.c.account_type)
                    .outerjoin(ConsumerProfile, ConsumerProfile.user_id == User.id)
                    .join(_COMPANIES, _COMPANIES.c.id == User.company_id)
                    .options(selectinload(User.preferences))
                    .where(User.id == user_id, User.company_id == company_id)
                )
            ).first()
            if row is None:
                await uow.commit()
                return None
            user, profile, account_type = row
            prefs = user.preferences
            if prefs is None:
                prefs = UserPreferences(user_id=user_id, company_id=company_id)
                uow.session.add(prefs)
            prefs.hide_spending = hide_spending
            await uow.commit()
        return _record(user, profile, account_type, prefs)

    async def set_avatar(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        avatar_key: uuid.UUID,
        content_type: str,
        data: bytes,
        updated_at: datetime,
    ) -> bool:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            prefs = await _get_preferences_or_create(uow, company_id, user_id)
            prefs.avatar_key = avatar_key
            prefs.avatar_content_type = content_type
            prefs.avatar_data = data
            prefs.avatar_updated_at = updated_at
            await uow.commit()
        return True

    async def clear_avatar(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            prefs = await uow.session.get(UserPreferences, user_id)
            if prefs is not None:
                prefs.avatar_key = None
                prefs.avatar_content_type = None
                prefs.avatar_data = None
                prefs.avatar_updated_at = None
                await uow.commit()
                return True
            return False

    async def get_avatar(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        avatar_key: uuid.UUID,
    ) -> AvatarBlob | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            prefs = await uow.session.get(UserPreferences, user_id)
            if prefs is None or prefs.avatar_key != avatar_key:
                return None
            if prefs.avatar_content_type is None or prefs.avatar_data is None or prefs.avatar_updated_at is None:
                return None
            return AvatarBlob(
                content_type=prefs.avatar_content_type,
                data=prefs.avatar_data,
                updated_at=prefs.avatar_updated_at,
            )

    async def get_preferences(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserPreferences | None:
        tenant = TenantContext(company_id=company_id, user_id=user_id)
        async with self._uow_factory.begin(tenant) as uow:
            prefs = await uow.session.get(UserPreferences, user_id)
            return prefs


def _record(
    user: User,
    profile: ConsumerProfile | None,
    account_type: object,
    prefs: UserPreferences | None = None,
) -> AccountRecord:
    if prefs is not None:
        display_currency_val = normalize_currency(prefs.display_currency)
        hide_spending_val = prefs.hide_spending
        avatar_key = prefs.avatar_key
    else:
        display_currency_val = "BRL"
        hide_spending_val = False
        avatar_key = None

    return AccountRecord(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        # birth_date, gender, postal_code estao em consumer_profiles (tabela antiga)
        birth_date=profile.birth_date if profile is not None else None,
        gender=profile.gender if profile is not None else None,
        postal_code=profile.postal_code if profile is not None else None,
        display_currency=display_currency_val,
        avatar_url=(
            account_avatar_url(user.company_id, user.id, avatar_key)
            if avatar_key is not None
            else None
        ),
        account_type=str(account_type),
        hide_spending=hide_spending_val,
    )
