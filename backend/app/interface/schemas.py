"""Schemas HTTP da fundacao: Problem Details (RFC 7807) e health."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FieldError(BaseModel):
    """Erro de validacao de um campo (sem ecoar o valor recebido)."""

    model_config = ConfigDict(frozen=True)

    field: str = Field(description="Caminho do campo, por exemplo items.0.quantity")
    message: str = Field(description="Descricao segura do problema")
    code: str = Field(description="Codigo estavel do erro de validacao")


class ProblemDetails(BaseModel):
    """application/problem+json (RFC 9457, compativel com RFC 7807).

    ``request_id`` correlaciona com o header ``X-Request-ID`` e com os logs.
    ``trace_id`` continua presente por compatibilidade com clientes antigos.
    """

    model_config = ConfigDict(frozen=True)

    type: str = Field(description="URI/identificador estavel do tipo de erro")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = Field(default=None, description="Caminho da requisicao")
    request_id: str | None = Field(
        default=None, description="ID de correlacao da requisicao (X-Request-ID)"
    )
    trace_id: str | None = Field(default=None, description="Trace ID W3C ou request ID")
    errors: list[FieldError] | None = Field(
        default=None, description="Erros por campo (somente em falhas de validacao)"
    )


class HealthResponse(BaseModel):
    """Resposta minima de liveness para monitores externos (sem dependencias)."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"


class LivenessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["alive"] = "alive"


class CheckStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class ReadinessResponse(BaseModel):
    """Mapa deterministico das dependencias essenciais (PostgreSQL, Redis)."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckStatus]


SearchHealthStatus = Literal["ok", "degraded", "unavailable", "disabled"]


class SearchHealthResponse(BaseModel):
    """Estado do motor de busca (nao essencial ao readiness da aplicacao)."""

    model_config = ConfigDict(frozen=True)

    status: SearchHealthStatus
    detail: str | None = None
