"""Regras compartilhadas de disponibilidade/CA de EPI (pure Python).

A regra de CA e compartilhada porque o catalogo (que expoe o estado) e os
contextos cart/ordering (que validam a venda) precisam da MESMA regra sem
acoplar-se entre si (bounded contexts independentes). Recebe tipos primitivos
para nao depender do vocabulario de um modulo especifico.

Estado do CA derivado de ``ca_valid_until`` (nunca armazenado em campo
redundante). Regra critica: ``is_epi`` e ``ca_valid_until < today`` -> nao vende.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum


class CaStatus(StrEnum):
    """Estado derivado do CA de um produto."""

    NOT_APPLICABLE = "NOT_APPLICABLE"  # produto nao EPI
    VALID = "VALID"
    EXPIRED = "EXPIRED"  # ca_valid_until < today
    MISSING = "MISSING"  # EPI sem data de CA


def ca_status(*, is_epi: bool, ca_valid_until: date | None, today: date) -> CaStatus:
    if not is_epi:
        return CaStatus.NOT_APPLICABLE
    if ca_valid_until is None:
        return CaStatus.MISSING
    if ca_valid_until < today:
        return CaStatus.EXPIRED
    return CaStatus.VALID


def is_ca_expired(*, is_epi: bool, ca_valid_until: date | None, today: date) -> bool:
    return is_epi and ca_valid_until is not None and ca_valid_until < today


def is_sellable(*, status: str, is_epi: bool, ca_valid_until: date | None, today: date) -> bool:
    """Produto pode ser vendido (status ACTIVE + CA de EPI valido)."""
    if status != "ACTIVE":
        return False
    if is_epi:
        return ca_valid_until is not None and ca_valid_until >= today
    return True
