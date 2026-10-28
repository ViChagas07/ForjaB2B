"""Tipos puros do dominio de IA (sem frameworks, sem I/O).

`Locale` e `GuardVerdict` sao vocabularios fechados; `AgentContext` e
`ToolResult` sao valores imutaveis que atravessam as camadas. Nenhum tipo
aqui importa langchain/langgraph/pydantic (contrato import-linter).
"""

from app.modules.ai.domain.audit_payload import build_audit_payload, sanitize_prefix
from app.modules.ai.domain.types import (
    AgentContext,
    GuardVerdict,
    Locale,
    ToolResult,
    resolve_locale,
)

__all__ = [
    "AgentContext",
    "GuardVerdict",
    "Locale",
    "ToolResult",
    "build_audit_payload",
    "resolve_locale",
    "sanitize_prefix",
]
