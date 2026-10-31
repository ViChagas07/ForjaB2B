"""Perfil da conta: leitura, normalizacao e validacao sem I/O."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from app.application.security import AuthContext
from app.domain.consumer import Gender
from app.modules.identity.application.account import (
    GetAccount,
    UpdateAccount,
    UpdateAccountCommand,
    UpdateAccountCurrency,
    UpdateAccountCurrencyCommand,
)
from app.modules.identity.application.errors import (
    AccountNotFoundError,
    InvalidAccountProfileError,
)
from app.modules.identity.application.ports import AccountRecord

_COMPANY = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_AUTH = AuthContext(
    user_id=_USER,
    company_id=_COMPANY,
    role="BUYER",
    token_id="account-test",
)
_TODAY = date(2026, 10, 30)


def _record(**overrides: Any) -> AccountRecord:
    base = AccountRecord(
        id=_USER,
        email="buyer@example.com",
        full_name="Comprador",
        phone="+55 11 99999-9999",
        birth_date=date(1990, 1, 1),
        gender=Gender.PREFIRO_NAO_INFORMAR,
        postal_code="01310100",
        display_currency="BRL",
        account_type="COMPANY",
    )
    return replace(base, **overrides)


class FakeRepository:
    def __init__(self, record: AccountRecord | None) -> None:
        self.record = record
        self.last_update: dict[str, Any] | None = None

    async def get(self, company_id: uuid.UUID, user_id: uuid.UUID) -> AccountRecord | None:
        return self.record

    async def update(self, **kwargs: Any) -> AccountRecord | None:
        if self.record is None:
            return None
        self.last_update = kwargs
        return _record(
            full_name=kwargs["full_name"],
            phone=kwargs["phone"],
            birth_date=kwargs["birth_date"] or self.record.birth_date,
            gender=kwargs["gender"] or self.record.gender,
            postal_code=kwargs["postal_code"] or self.record.postal_code,
            display_currency=self.record.display_currency,
        )

    async def update_display_currency(self, **kwargs: Any) -> AccountRecord | None:
        if self.record is None:
            return None
        self.last_update = kwargs
        self.record = replace(self.record, display_currency=kwargs["display_currency"])
        return self.record


async def test_get_account_devolve_perfil() -> None:
    result = await GetAccount(repository=FakeRepository(_record())).execute(_AUTH)
    assert result.email == "buyer@example.com"
    assert result.role == "BUYER"
    assert result.postal_code == "01310100"


async def test_get_account_inexistente_404() -> None:
    with pytest.raises(AccountNotFoundError):
        await GetAccount(repository=FakeRepository(None)).execute(_AUTH)


async def test_update_normaliza_nome_telefone_e_cep() -> None:
    repository = FakeRepository(_record())
    result = await UpdateAccount(repository=repository, today=_TODAY).execute(
        _AUTH,
        UpdateAccountCommand(
            full_name="  Novo Nome  ",
            phone=" +55 (11) 98888-7777 ",
            birth_date=date(1992, 5, 10),
            gender=Gender.FEMININO,
            postal_code="01310-100",
        ),
    )
    assert result.full_name == "Novo Nome"
    assert result.phone == "+55 (11) 98888-7777"
    assert result.postal_code == "01310100"
    assert repository.last_update is not None
    assert repository.last_update["postal_code"] == "01310100"


@pytest.mark.parametrize("name", ["", " A "])
async def test_nome_invalido(name: str) -> None:
    with pytest.raises(InvalidAccountProfileError):
        await UpdateAccount(repository=FakeRepository(_record()), today=_TODAY).execute(
            _AUTH, UpdateAccountCommand(full_name=name)
        )


async def test_cep_invalido() -> None:
    with pytest.raises(InvalidAccountProfileError):
        await UpdateAccount(repository=FakeRepository(_record()), today=_TODAY).execute(
            _AUTH, UpdateAccountCommand(full_name="Nome", postal_code="123")
        )


async def test_data_futura_ou_menor_de_idade() -> None:
    use_case = UpdateAccount(repository=FakeRepository(_record()), today=_TODAY)
    with pytest.raises(InvalidAccountProfileError):
        await use_case.execute(
            _AUTH,
            UpdateAccountCommand(full_name="Nome", birth_date=date(2010, 1, 1)),
        )
    with pytest.raises(InvalidAccountProfileError):
        await use_case.execute(
            _AUTH,
            UpdateAccountCommand(full_name="Nome", birth_date=date(2030, 1, 1)),
        )


async def test_telefone_invalido() -> None:
    with pytest.raises(InvalidAccountProfileError):
        await UpdateAccount(repository=FakeRepository(_record()), today=_TODAY).execute(
            _AUTH,
            UpdateAccountCommand(full_name="Nome", phone="telefone<script>"),
        )


async def test_update_de_usuario_ausente_404() -> None:
    with pytest.raises(AccountNotFoundError):
        await UpdateAccount(repository=FakeRepository(None), today=_TODAY).execute(
            _AUTH, UpdateAccountCommand(full_name="Nome")
        )


async def test_moeda_de_exibicao_e_normalizada_e_persistida() -> None:
    repository = FakeRepository(_record())
    result = await UpdateAccountCurrency(repository=repository).execute(
        _AUTH, UpdateAccountCurrencyCommand(display_currency=" usd ")
    )

    assert result.display_currency == "USD"
    assert repository.last_update is not None
    assert repository.last_update["display_currency"] == "USD"


async def test_moeda_fora_da_lista_cai_em_brl() -> None:
    repository = FakeRepository(_record(display_currency="USD"))
    result = await UpdateAccountCurrency(repository=repository).execute(
        _AUTH, UpdateAccountCurrencyCommand(display_currency="CHF")
    )

    assert result.display_currency == "BRL"

    repository = FakeRepository(_record(display_currency="USD"))
    result = await UpdateAccountCurrency(repository=repository).execute(
        _AUTH, UpdateAccountCurrencyCommand(display_currency="")
    )
    assert result.display_currency == "BRL"


async def test_leitura_normaliza_moeda_invalida_do_banco() -> None:
    repository = FakeRepository(_record(display_currency="CHF"))

    profile = await GetAccount(repository=repository).execute(_AUTH)

    assert profile.display_currency == "BRL"


async def test_moeda_de_usuario_ausente_404() -> None:
    with pytest.raises(AccountNotFoundError):
        await UpdateAccountCurrency(repository=FakeRepository(None)).execute(
            _AUTH, UpdateAccountCurrencyCommand(display_currency="USD")
        )
