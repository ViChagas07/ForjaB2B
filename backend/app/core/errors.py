"""Erros base da aplicacao.

AppError e a raiz de todos os erros esperados da aplicacao. O mapeamento
para HTTP (RFC 7807) acontece na camada de interface. Erros de dominio
(DomainError) vivem em app.domain.errors e sao convertidos pela interface.

Nenhuma regra de negocio aqui: apenas o contrato transversal de erro.
"""

from __future__ import annotations


class AppError(Exception):
    """Erro de aplicacao com metadados estaveis para Problem Details (RFC 7807).

    `code` e o identificador estavel consumido por clientes (campo `type`).
    `detail` nunca deve conter segredos, credenciais ou PII.
    """

    status_code: int = 500
    title: str = "Internal Server Error"
    code: str = "internal_error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title


class ServiceUnavailableError(AppError):
    """Dependencia de infraestrutura indisponivel."""

    status_code = 503
    title = "Service Unavailable"
    code = "service_unavailable"


class ConfigurationError(AppError):
    """Configuracao obrigatoria ausente ou invalida."""

    status_code = 500
    title = "Configuration Error"
    code = "configuration_error"
