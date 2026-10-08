"""Testes unitarios da validacao real de CNPJ (digitos verificadores)."""

from __future__ import annotations

import pytest

from app.modules.companies.domain.cnpj import is_valid_cnpj, normalize_cnpj, validate_cnpj
from app.modules.companies.domain.errors import InvalidCnpjError

_VALID_CNPJ = "11222333000181"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("11.222.333/0001-81", _VALID_CNPJ),
        ("11222333000181", _VALID_CNPJ),
        ("  11.222.333/0001-81 ", _VALID_CNPJ),
    ],
)
def test_normaliza_removendo_mascara(raw: str, expected: str) -> None:
    assert normalize_cnpj(raw) == expected


@pytest.mark.parametrize(
    "cnpj",
    [
        _VALID_CNPJ,
        "11444777000161",  # CNPJ do seed da Fase 1
    ],
)
def test_cnpj_valido(cnpj: str) -> None:
    assert is_valid_cnpj(cnpj) is True


@pytest.mark.parametrize(
    "cnpj",
    [
        "11222333000182",  # digito verificador errado
        "11222333000180",  # digito verificador errado
        "00000000000000",  # sequencia repetida
        "11111111111111",
        "123",  # tamanho invalido
        "1122233300018",  # 13 digitos
        "",
    ],
)
def test_cnpj_invalido(cnpj: str) -> None:
    assert is_valid_cnpj(cnpj) is False


def test_validate_cnpj_retorna_normalizado() -> None:
    assert validate_cnpj("11.222.333/0001-81") == _VALID_CNPJ


def test_validate_cnpj_invalido_levanta_erro() -> None:
    with pytest.raises(InvalidCnpjError):
        validate_cnpj("11222333000182")
