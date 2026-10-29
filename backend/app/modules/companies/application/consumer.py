"""Caso de uso do cadastro de cliente consumidor (conta CPF).

O consumidor e uma conta ``PERSON`` na raiz do tenant: a empresa pessoal e
criada ja ACTIVE (sem aprovacao manual), o usuario entra como ``BUYER`` (nunca
``ADMIN``, para nao herdar acesso administrativo) e o perfil pessoal fica em
``consumer_profiles``. A unicidade de e-mail/CPF continua global em ``users``.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import date

from app.modules.companies.application.errors import (
    ConsentRequiredError,
    InvalidBirthDateError,
    InvalidPostalCodeError,
)
from app.modules.companies.application.ports import (
    CompanyRecord,
    CompanyRepository,
    ConsentRecordData,
    ConsumerProfileRecord,
    CpfHasher,
    OperatorRecord,
    PasswordHasher,
)
from app.modules.companies.domain.cpf import validate_cpf
from app.modules.companies.domain.enums import AccountType, CompanyStatus

_NON_DIGITS = re.compile(r"\D")

# Valores do vocabulario identity (mantidos locais para nao importar identity).
_BUYER_ROLE = "BUYER"
_MEMBER_ACTIVE = "ACTIVE"
_USER_ACTIVE = "ACTIVE"

_MIN_AGE = 18
_MAX_AGE = 120

_TERMS_VERSION = "v1.0"
_PRIVACY_VERSION = "v1.0"
_TERMS_DOCUMENT_HASH = hashlib.sha256(b"forja-terms-v1.0").hexdigest()
_PRIVACY_DOCUMENT_HASH = hashlib.sha256(b"forja-privacy-v1.0").hexdigest()


@dataclass(frozen=True, kw_only=True)
class RegisterConsumerCommand:
    """Entrada do cadastro de consumidor (dados minimos para abrir a conta)."""

    full_name: str
    email: str
    password: str
    cpf: str
    birth_date: date
    postal_code: str
    gender: str
    consent: bool


@dataclass(frozen=True, kw_only=True)
class ConsumerRegistered:
    """Resultado do cadastro de consumidor."""

    company_id: uuid.UUID
    user_id: uuid.UUID


class RegisterConsumer:
    """Caso de uso: cria a conta pessoal, o usuario e o perfil do consumidor."""

    def __init__(
        self,
        *,
        repository: CompanyRepository,
        password_hasher: PasswordHasher,
        cpf_hasher: CpfHasher,
        today: date | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._cpf_hasher = cpf_hasher
        self._today = today or date.today()

    async def register(self, command: RegisterConsumerCommand) -> ConsumerRegistered:
        if not command.consent:
            raise ConsentRequiredError()

        cpf = validate_cpf(command.cpf)
        postal_code = _normalize_postal_code(command.postal_code)
        if len(postal_code) != 8:
            raise InvalidPostalCodeError()
        _validate_birth_date(command.birth_date, today=self._today)

        company_id = uuid.uuid4()
        user_id = uuid.uuid4()
        full_name = command.full_name.strip()

        company = CompanyRecord(
            id=company_id,
            cnpj=None,
            legal_name=full_name,
            trade_name=None,
            status=CompanyStatus.ACTIVE.value,
            account_type=AccountType.PERSON.value,
        )
        operator = OperatorRecord(
            user_id=user_id,
            member_id=uuid.uuid4(),
            full_name=full_name,
            email=command.email.strip().lower(),
            cpf_hash=self._cpf_hasher.hash(cpf),
            password_hash=self._password_hasher.hash(command.password),
            user_status=_USER_ACTIVE,
            role=_BUYER_ROLE,
            member_status=_MEMBER_ACTIVE,
        )
        profile = ConsumerProfileRecord(
            birth_date=command.birth_date,
            gender=command.gender,
            postal_code=postal_code,
        )
        consents = (
            ConsentRecordData(
                purpose="TERMS",
                action="GRANTED",
                version=_TERMS_VERSION,
                document_hash=_TERMS_DOCUMENT_HASH,
            ),
            ConsentRecordData(
                purpose="PRIVACY",
                action="GRANTED",
                version=_PRIVACY_VERSION,
                document_hash=_PRIVACY_DOCUMENT_HASH,
            ),
        )

        await self._repository.add_consumer(company, operator, profile, consents)
        return ConsumerRegistered(company_id=company_id, user_id=user_id)


def _normalize_postal_code(raw: str) -> str:
    return _NON_DIGITS.sub("", raw)


def _validate_birth_date(birth_date: date, *, today: date) -> None:
    age = _age_on(birth_date, today=today)
    if age < _MIN_AGE:
        raise InvalidBirthDateError("E necessario ter 18 anos ou mais para criar a conta.")
    if age > _MAX_AGE:
        raise InvalidBirthDateError("Data de nascimento invalida.")


def _age_on(birth_date: date, *, today: date) -> int:
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
