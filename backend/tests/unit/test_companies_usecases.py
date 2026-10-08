"""Testes unitarios dos casos de uso do contexto de empresas (com fakes)."""

from __future__ import annotations

import uuid

import pytest

from app.modules.companies.application.company import (
    GetCurrentCompany,
    RegisterCompany,
    RegisterCompanyCommand,
)
from app.modules.companies.application.errors import CompanyAlreadyExistsError, CompanyNotFoundError
from app.modules.companies.application.ports import CompanyRecord, OperatorRecord
from app.modules.companies.domain.errors import InvalidCnpjError

_VALID_CNPJ = "11222333000181"


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"


class FakeCpfHasher:
    def hash(self, cpf: str) -> str:
        return f"cpf:{cpf}"


class FakeRepository:
    def __init__(self, *, existing_cnpjs: set[str] | None = None) -> None:
        self._existing_cnpjs = existing_cnpjs or set()
        self.added: tuple[CompanyRecord, OperatorRecord] | None = None

    async def add(self, company: CompanyRecord, operator: OperatorRecord) -> None:
        if company.cnpj in self._existing_cnpjs:
            raise CompanyAlreadyExistsError()
        self.added = (company, operator)

    async def get_by_id(self, company_id: uuid.UUID) -> CompanyRecord | None:
        return None


def _command(
    *,
    cnpj: str = "11.222.333/0001-81",
    legal_name: str = "Empresa Teste Ltda",
    trade_name: str | None = "Empresa Teste",
    admin_full_name: str = "Admin Teste",
    admin_email: str = "admin@teste.com",
    admin_cpf: str = "529.982.247-25",
    password: str = "Senha@Forte123",  # noqa: S107 - senha de teste, nao segredo
) -> RegisterCompanyCommand:
    return RegisterCompanyCommand(
        cnpj=cnpj,
        legal_name=legal_name,
        trade_name=trade_name,
        admin_full_name=admin_full_name,
        admin_email=admin_email,
        admin_cpf=admin_cpf,
        password=password,
    )


async def test_registro_sucesso_normaliza_cnpj_e_hash_senha_cpf() -> None:
    repo = FakeRepository()
    use_case = RegisterCompany(
        repository=repo, password_hasher=FakePasswordHasher(), cpf_hasher=FakeCpfHasher()
    )
    result = await use_case.register(_command())

    assert result.cnpj == _VALID_CNPJ
    assert result.status == "PENDING"
    assert repo.added is not None
    company, operator = repo.added
    assert company.cnpj == _VALID_CNPJ
    assert operator.password_hash == "hashed:Senha@Forte123"
    assert operator.cpf_hash == "cpf:52998224725"
    assert operator.user_status == "PENDING_APPROVAL"
    assert operator.role == "ADMIN"
    assert operator.member_status == "ACTIVE"


async def test_registro_cnpj_invalido() -> None:
    repo = FakeRepository()
    use_case = RegisterCompany(
        repository=repo, password_hasher=FakePasswordHasher(), cpf_hasher=FakeCpfHasher()
    )
    with pytest.raises(InvalidCnpjError):
        await use_case.register(_command(cnpj="11222333000182"))


async def test_registro_cnpj_duplicado_409() -> None:
    repo = FakeRepository(existing_cnpjs={_VALID_CNPJ})
    use_case = RegisterCompany(
        repository=repo, password_hasher=FakePasswordHasher(), cpf_hasher=FakeCpfHasher()
    )
    with pytest.raises(CompanyAlreadyExistsError):
        await use_case.register(_command())


async def test_get_empresa_nao_encontrada_404() -> None:
    use_case = GetCurrentCompany(repository=FakeRepository())
    with pytest.raises(CompanyNotFoundError):
        await use_case.get(uuid.uuid4())
