"""Regras de dominio de identidade (pure Python, sem frameworks).

Politica de senha minima: evita credenciais triviais no cadastro. O hash em si
(Argon2id) e responsabilidade da infraestrutura; aqui fica apenas a regra de
negocio sobre a forca da senha em texto plano.
"""

from __future__ import annotations

from app.modules.identity.domain.errors import WeakPasswordError

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def validate_password_strength(password: str) -> None:
    """Valida a politica de senha; levanta WeakPasswordError quando violada."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(f"A senha deve ter no maximo {MAX_PASSWORD_LENGTH} caracteres.")
