"""Erros de dominio do contexto de empresas (pure Python)."""

from __future__ import annotations

from app.domain.errors import DomainError


class InvalidCnpjError(DomainError):
    """CNPJ com formato ou digitos verificadores invalidos."""

    code = "invalid_cnpj"
