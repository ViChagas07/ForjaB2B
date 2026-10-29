"""Testes unitarios do cadastro de cliente consumidor (com fakes)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.modules.companies.application.consumer import (
    RegisterConsumer,
    RegisterConsumerCommand,
)
from app.modules.companies.application.errors import (
    ConsentRequiredError,
    InvalidBirthDateError,
    InvalidPostalCodeError,
)
from app.modules.companies.application.ports import (
    CompanyRecord,
    ConsentRecordData,
    ConsumerProfileRecord,
    OperatorRecord,
)
from app.modules.companies.domain.errors import InvalidCpfError

_VALID_CPF = "529.982.247-25"


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"


class FakeCpfHasher:
    def hash(self, cpf: str) -> str:
        return f"cpf:{cpf}"


class FakeRepository:
    def __init__(self) -> None:
        self.consumer: tuple[
            CompanyRecord,
            OperatorRecord,
            ConsumerProfileRecord,
            tuple[ConsentRecordData, ...],
        ] | None = None

    async def add(self, company: CompanyRecord, operator: OperatorRecord) -> None:
        raise AssertionError("add nao deveria ser chamado no cadastro de consumidor")

    async def add_consumer(
        self,
        company: CompanyRecord,
        operator: OperatorRecord,
        profile: ConsumerProfileRecord,
        consents: tuple[ConsentRecordData, ...],
    ) -> None:
        self.consumer = (company, operator, profile, consents)

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRecord | None:
        return None

    async def approve(self, company_id: uuid.UUID) -> bool:
        return False


def _command(
    *,
    cpf: str = _VALID_CPF,
    birth_date: date = date(1990, 1, 1),
    postal_code: str = "01001-000",
    consent: bool = True,
) -> RegisterConsumerCommand:
    return RegisterConsumerCommand(
        full_name="Cliente Teste",
        email="CLIENTE@TESTE.COM",
        password="Senha@Forte123",
        cpf=cpf,
        birth_date=birth_date,
        postal_code=postal_code,
        gender="PREFIRO_NAO_INFORMAR",
        consent=consent,
    )


def _usecase(repository: FakeRepository, *, today: date = date(2026, 10, 29)) -> RegisterConsumer:
    return RegisterConsumer(
        repository=repository,
        password_hasher=FakePasswordHasher(),
        cpf_hasher=FakeCpfHasher(),
        today=today,
    )


async def test_registro_sucesso_cria_conta_pessoal_ativa() -> None:
    repository = FakeRepository()
    result = await _usecase(repository).register(_command())

    assert result.company_id
    assert result.user_id
    assert repository.consumer is not None
    company, operator, profile, consents = repository.consumer
    assert company.account_type == "PERSON"
    assert company.cnpj is None
    assert company.status == "ACTIVE"
    assert company.legal_name == "Cliente Teste"
    assert operator.email == "cliente@teste.com"
    assert operator.user_status == "ACTIVE"
    assert operator.role == "BUYER"
    assert operator.member_status == "ACTIVE"
    assert operator.password_hash == "hashed:Senha@Forte123"
    assert operator.cpf_hash == "cpf:52998224725"
    assert profile.birth_date == date(1990, 1, 1)
    assert profile.postal_code == "01001000"
    assert [consent.purpose for consent in consents] == ["TERMS", "PRIVACY"]
    assert all(consent.action == "GRANTED" for consent in consents)


async def test_registro_exige_consentimento() -> None:
    with pytest.raises(ConsentRequiredError):
        await _usecase(FakeRepository()).register(_command(consent=False))


async def test_registro_rejeita_cpf_invalido() -> None:
    with pytest.raises(InvalidCpfError):
        await _usecase(FakeRepository()).register(_command(cpf="529.982.247-26"))


async def test_registro_rejeita_menor_de_idade() -> None:
    with pytest.raises(InvalidBirthDateError):
        await _usecase(FakeRepository()).register(_command(birth_date=date(2015, 1, 1)))


async def test_registro_rejeita_cep_invalido() -> None:
    with pytest.raises(InvalidPostalCodeError):
        await _usecase(FakeRepository()).register(_command(postal_code="123"))
