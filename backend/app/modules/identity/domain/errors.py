"""Erros de dominio do contexto de identidade (pure Python)."""

from __future__ import annotations

from app.domain.errors import DomainError


class WeakPasswordError(DomainError):
    """Senha abaixo da politica minima de forca exigida no cadastro."""

    code = "weak_password"
