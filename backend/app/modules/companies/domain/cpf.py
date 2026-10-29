"""Validacao real de CPF (normalizacao + digitos verificadores).

O CPF nunca e persistido em texto plano (apenas HMAC-SHA256), mas a validacao
estrutural no servidor evita que um cliente malicioso burle a checagem do
frontend e crie uma conta com documentos invalidos. CNPJ e CPF compartilham o
mesmo algoritmo de modulo 11, com pesos diferentes.
"""

from __future__ import annotations

import re

from app.modules.companies.domain.errors import InvalidCpfError

CPF_LENGTH = 11

_NON_DIGITS = re.compile(r"\D")


def normalize_cpf(raw: str) -> str:
    """Remove a mascara do CPF (mantem apenas digitos)."""
    return _NON_DIGITS.sub("", raw)


def is_valid_cpf(raw: str) -> bool:
    """Valida formato (11 digitos) e os dois digitos verificadores."""
    digits = normalize_cpf(raw)
    if len(digits) != CPF_LENGTH:
        return False
    if digits == digits[0] * CPF_LENGTH:
        return False
    base = digits[:9]
    first = _check_digit(base, 10)
    second = _check_digit(base + first, 11)
    return digits == base + first + second


def validate_cpf(raw: str) -> str:
    """Normaliza e valida; devolve os 11 digitos ou levanta InvalidCpfError."""
    digits = normalize_cpf(raw)
    if not is_valid_cpf(digits):
        raise InvalidCpfError("CPF invalido.")
    return digits


def _check_digit(base: str, factor: int) -> str:
    total = 0
    for digit in base:
        total += int(digit) * factor
        factor -= 1
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)
