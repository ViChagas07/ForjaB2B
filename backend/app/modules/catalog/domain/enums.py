"""Vocabulario de estado do modulo catalog (pure Python, sem frameworks)."""

from __future__ import annotations

from enum import StrEnum


class ProductStatus(StrEnum):
    """Disponibilidade de um produto no catalogo."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
