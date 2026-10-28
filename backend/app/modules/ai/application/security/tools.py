"""Registro de ferramentas por allowlist de no e guard de chamadas (item D.8).

- Ferramentas sao declaradas com schema Pydantic STRICT (`extra="forbid"`,
  tipos/tamanhos/regex de IDs) e ficam visiveis ao modelo APENAS no no do
  grafo em que foram registradas (`tools_for_node`).
- Ferramentas do chat sao SOMENTE LEITURA: acoes com efeito colateral nao
  sao ferramentas — ficam em codigo deterministico fora do LLM.
- `ToolCallGuard` (instancia por turno): no maximo `max_calls` chamadas por
  turno, uma chamada unica por (nome, argumentos) — dedupe canonicamente;
- identidade (company_id/user_id) e REMOVIDA dos argumentos do modelo e
  injetada pelo servidor depois, fora do alcance do LLM.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.ai.domain.security.injection import VerdictLevel
from app.modules.ai.domain.security.tool_args import (
    scan_tool_arguments,
    strip_identity_arguments,
)

MAX_TOOL_CALLS_PER_TURN = 4


class ToolSchema(BaseModel):
    """Base dos schemas de ferramenta: estrito, sem campos extras."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


@dataclass(frozen=True, kw_only=True)
class ToolSpec:
    """Ferramenta SOMENTE LEITURA visivel a nos especificos do grafo."""

    name: str
    description: str
    schema: type[ToolSchema]
    allowed_nodes: frozenset[str]


class ToolRegistry:
    """Allowlist por no: o modelo so enxerga as ferramentas do no atual."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._by_node: dict[str, list[ToolSpec]] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.allowed_nodes == frozenset():
            raise ValueError("ferramenta precisa de ao menos um no")
        self._specs[spec.name] = spec
        for node in spec.allowed_nodes:
            self._by_node.setdefault(node, []).append(spec)

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def tools_for_node(self, node: str) -> tuple[ToolSpec, ...]:
        return tuple(self._by_node.get(node, ()))

    def prompt_description(self, node: str) -> str:
        """Descricao compacta (nome + campos) das ferramentas do no."""
        return "; ".join(
            f"{spec.name}({', '.join(spec.schema.model_fields)}): {spec.description}"
            for spec in self.tools_for_node(node)
        )


@dataclass(frozen=True, kw_only=True)
class ToolCallDecision:
    """Resultado do guard sobre uma chamada de ferramenta do modelo."""

    accepted: bool
    reason_code: str | None = None
    args: BaseModel | None = None
    actions: tuple[str, ...] = field(default_factory=tuple)


class ToolCallGuard:
    """Guard por turno: allowlist, schema estrito, limites e dedupe."""

    def __init__(self, *, registry: ToolRegistry, max_calls: int = MAX_TOOL_CALLS_PER_TURN) -> None:
        self._registry = registry
        self._max_calls = max_calls
        self._calls = 0
        self._seen: set[tuple[str, str]] = set()

    def inspect(self, *, node: str, name: str, raw_args: Mapping[str, object]) -> ToolCallDecision:
        spec = self._registry.spec(name)
        if spec is None:
            return ToolCallDecision(accepted=False, reason_code="tool_desconhecida")
        if node not in spec.allowed_nodes:
            return ToolCallDecision(accepted=False, reason_code="tool_fora_do_no")
        if self._calls >= self._max_calls:
            return ToolCallDecision(accepted=False, reason_code="tool_limite_por_turno")

        cleaned = strip_identity_arguments(raw_args)
        actions: list[str] = []
        if len(cleaned) != len(raw_args):
            actions.append("identidade_removida")  # forjada pelo modelo: audit

        verdict = scan_tool_arguments(cleaned)
        if verdict.level == VerdictLevel.BLOCK:
            return ToolCallDecision(
                accepted=False, reason_code=verdict.reason_code, actions=tuple(actions)
            )

        try:
            parsed_args = spec.schema.model_validate(cleaned)
        except (ValidationError, TypeError, ValueError):
            return ToolCallDecision(
                accepted=False, reason_code="tool_args_invalidos", actions=tuple(actions)
            )

        canonical = json.dumps(cleaned, sort_keys=True, default=str)
        dedupe_key = (name, canonical)
        if dedupe_key in self._seen:
            return ToolCallDecision(
                accepted=False, reason_code="tool_chamada_duplicada", actions=tuple(actions)
            )
        self._seen.add(dedupe_key)
        self._calls += 1
        return ToolCallDecision(accepted=True, args=parsed_args, actions=tuple(actions))


def assert_read_only(spec: ToolSpec) -> None:
    """Contrato de superficie: toda ToolSpec e somente leitura.

    Acoes com efeito colateral (enviar mensagem, criar oferta, alterar
    carrinho) NUNCA se registram como ferramenta do LLM — ficam em codigo
    deterministico apos decisao estruturada validada (FASE 3).
    """
    if not issubclass(spec.schema, ToolSchema):
        raise ValueError("ferramenta fora do contrato somente leitura (ToolSchema)")
    if spec.allowed_nodes == frozenset():
        raise ValueError("ferramenta precisa de ao menos um no")


def model_tool_call_payload(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Formato canonico que o grafo recebe do modelo ({name, arguments})."""
    return {"name": name, "arguments": args}
