"""Erros de dominio, independentes de qualquer framework.

A camada de interface mapeia DomainError para Problem Details (RFC 7807).
Nunca usar excecoes de infraestrutura (SQLAlchemy, HTTP) no dominio.
"""

from __future__ import annotations


class DomainError(Exception):
    """Erro de regra de negocio com codigo estavel.

    `code` e o identificador estavel consumido pela camada de interface
    para compor o `type` do Problem Details.
    """

    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
