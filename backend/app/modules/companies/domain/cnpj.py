"""Validacao real de CNPJ (normalizacao + digitos verificadores).

Nao basta uma regex de formato: os dois digitos verificadores sao recalculados
a partir dos 12 primeiros digitos conforme o algoritmo oficial (modulo 11).
Tambem rejeita sequencias repetidas (ex.: 00000000000000). O armazenamento e
sempre normalizado em 14 digitos; a unicidade e garantida pela constraint
``uq_companies_cnpj`` no banco.
"""

from __future__ import annotations

import re

from app.modules.companies.domain.errors import InvalidCnpjError

CNPJ_LENGTH = 14

_NON_DIGITS = re.compile(r"\D")

_FIRST_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_cnpj(raw: str) -> str:
    """Remove mascara (pontos, barra, hifen, espacos), mantendo apenas digitos."""
    return _NON_DIGITS.sub("", raw)


def is_valid_cnpj(cnpj: str) -> bool:
    """Valida formato (14 digitos) e os dois digitos verificadores."""
    digits = normalize_cnpj(cnpj)
    if len(digits) != CNPJ_LENGTH:
        return False
    if digits == digits[0] * CNPJ_LENGTH:
        return False
    first = _check_digit(digits[:12], _FIRST_WEIGHTS)
    second = _check_digit(digits[:12] + first, _SECOND_WEIGHTS)
    return digits == digits[:12] + first + second


def validate_cnpj(raw: str) -> str:
    """Normaliza e valida; devolve os 14 digitos ou levanta InvalidCnpjError."""
    digits = normalize_cnpj(raw)
    if not is_valid_cnpj(digits):
        raise InvalidCnpjError("CNPJ invalido.")
    return digits


def _check_digit(base: str, weights: tuple[int, ...]) -> str:
    total = sum(int(digit) * weight for digit, weight in zip(base, weights, strict=True))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)
