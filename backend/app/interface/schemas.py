"""Schemas HTTP da fundacao: Problem Details (RFC 7807) e health."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetails(BaseModel):
    """application/problem+json conforme RFC 7807."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(description="URI/identificador estavel do tipo de erro")
    title: str
    status: int
    detail: str | None = None
    instance: str | None = Field(default=None, description="Caminho da requisicao")
    trace_id: str | None = Field(default=None, description="Trace ID W3C ou request ID")


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
