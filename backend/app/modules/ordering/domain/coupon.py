"""Vocabulario e normalizacao de cupons de desconto (pure Python).

O codigo e normalizado (trim + maiusculas) e restrito a A-Z, 0-9, hifen e
underscore, com 4 a 32 caracteres. Estas funcoes sao a fonte unica para a API;
o banco repete o formato em CHECK para impedir dado fora do padrao.
"""

from __future__ import annotations

import re
from enum import StrEnum

COUPON_CODE_MIN_LENGTH = 4
COUPON_CODE_MAX_LENGTH = 32
_COUPON_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{4,32}$")


class CouponType(StrEnum):
    """Escopo do desconto: total dos produtos ou valor do frete."""

    PRODUCT_TOTAL = "PRODUCT_TOTAL"
    SHIPPING = "SHIPPING"


class CouponRedemptionStatus(StrEnum):
    """Ciclo de vida do resgate de um cupom em um pedido."""

    APPLIED = "APPLIED"
    RELEASED = "RELEASED"


def normalize_coupon_code(code: str) -> str:
    """Remove espacos das pontas e converte o codigo para maiusculas."""
    return code.strip().upper()


def is_valid_coupon_code(code: str) -> bool:
    """Indica se o codigo respeita o formato aceito pelo banco."""
    return _COUPON_CODE_PATTERN.fullmatch(code) is not None
