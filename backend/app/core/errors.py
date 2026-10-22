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
    headers: dict[str, str] | None = None

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title


class RateLimitExceededError(AppError):
    """Limite de requisicoes excedido (429 com Retry-After)."""

    status_code = 429
    title = "Too Many Requests"
    code = "rate_limit_exceeded"

    def __init__(
        self,
        *,
        retry_after_seconds: int,
        limit: int | None = None,
        remaining: int = 0,
        reset_after_seconds: int | None = None,
    ) -> None:
        retry = max(1, retry_after_seconds)
        super().__init__("Muitas requisicoes. Tente novamente mais tarde.")
        self.retry_after_seconds = retry
        self.headers = {"Retry-After": str(retry)}
        if limit is not None:
            self.headers["RateLimit-Limit"] = str(limit)
            self.headers["RateLimit-Remaining"] = str(max(0, remaining))
            self.headers["RateLimit-Reset"] = str(
                max(1, reset_after_seconds if reset_after_seconds is not None else retry)
            )


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
