"""Perfil da propria conta (nome, telefone, nascimento, genero e CEP)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date

from app.application.security import AuthContext
from app.domain.consumer import Gender
from app.domain.currency import normalize_currency
from app.modules.identity.application.errors import (
    AccountNotFoundError,
    InvalidAccountProfileError,
)
from app.modules.identity.application.ports import AccountRecord, AccountRepository

_NON_DIGITS = re.compile(r"\D")
_MIN_AGE = 18
_MAX_AGE = 120


@dataclass(frozen=True, kw_only=True)
class AccountProfile:
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    birth_date: date | None
    gender: Gender | None
    postal_code: str | None
    display_currency: str
    account_type: str
    role: str


@dataclass(frozen=True, kw_only=True)
class UpdateAccountCommand:
    full_name: str
    phone: str | None = None
    birth_date: date | None = None
    gender: Gender | None = None
    postal_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateAccountCurrencyCommand:
    display_currency: str


class GetAccount:
    def __init__(self, *, repository: AccountRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext) -> AccountProfile:
        record = await self._repository.get(auth.company_id, auth.user_id)
        if record is None:
            raise AccountNotFoundError()
        return _to_profile(record, role=auth.role)


class UpdateAccount:
    def __init__(self, *, repository: AccountRepository, today: date | None = None) -> None:
        self._repository = repository
        self._today = today or date.today()

    async def execute(self, auth: AuthContext, command: UpdateAccountCommand) -> AccountProfile:
        full_name = command.full_name.strip()
        if len(full_name) < 2 or len(full_name) > 200:
            raise InvalidAccountProfileError("Informe um nome com 2 a 200 caracteres.")

        phone = command.phone.strip() if command.phone else None
        if phone:
            if len(phone) > 20 or not re.fullmatch(r"[0-9+()\-\s]+", phone):
                raise InvalidAccountProfileError("Telefone invalido.")
        else:
            phone = None

        if command.birth_date is not None:
            age = _age_on(command.birth_date, today=self._today)
            if command.birth_date > self._today or age < _MIN_AGE or age > _MAX_AGE:
                raise InvalidAccountProfileError("Data de nascimento invalida.")

        postal_code = _normalize_postal_code(command.postal_code)
        if command.postal_code and len(postal_code) != 8:
            raise InvalidAccountProfileError("Informe um CEP com 8 digitos.")

        record = await self._repository.update(
            company_id=auth.company_id,
            user_id=auth.user_id,
            full_name=full_name,
            phone=phone,
            birth_date=command.birth_date,
            gender=command.gender,
            postal_code=postal_code or None,
        )
        if record is None:
            raise AccountNotFoundError()
        return _to_profile(record, role=auth.role)


class UpdateAccountCurrency:
    """Atualiza apenas a moeda de exibicao, sem tocar nos demais dados."""

    def __init__(self, *, repository: AccountRepository) -> None:
        self._repository = repository

    async def execute(
        self, auth: AuthContext, command: UpdateAccountCurrencyCommand
    ) -> AccountProfile:
        display_currency = normalize_currency(command.display_currency)
        record = await self._repository.update_display_currency(
            company_id=auth.company_id,
            user_id=auth.user_id,
            display_currency=display_currency,
        )
        if record is None:
            raise AccountNotFoundError()
        return _to_profile(record, role=auth.role)


def _normalize_postal_code(raw: str | None) -> str:
    return _NON_DIGITS.sub("", raw or "")


def _age_on(birth_date: date, *, today: date) -> int:
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def _to_profile(record: AccountRecord, *, role: str) -> AccountProfile:
    return AccountProfile(
        id=record.id,
        email=record.email,
        full_name=record.full_name,
        phone=record.phone,
        birth_date=record.birth_date,
        gender=record.gender,
        postal_code=record.postal_code,
        display_currency=record.display_currency,
        account_type=record.account_type,
        role=role,
    )
