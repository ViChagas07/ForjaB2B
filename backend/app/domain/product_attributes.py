"""Definição e validação de atributos de produto (domínio puro, sem frameworks).

Este módulo define:
1. Tipos de atributo suportados (text, number, enum, boolean)
2. Definição de atributo (chave, rótulo, tipo, escopo, opções, etc.)
3. Validador/normalizador de valores contra as definições
4. Validação dos campos obrigatórios do produto (nome, descrição, marca)
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Tipos e Enums
# ---------------------------------------------------------------------------


class AttributeType(StrEnum):
    """Tipos de atributo suportados."""

    TEXT = "text"
    NUMBER = "number"
    ENUM = "enum"
    BOOLEAN = "boolean"


class ScopeType(StrEnum):
    """Tipo de escopo da definição."""

    GLOBAL = "global"
    CATEGORIES = "categories"


@dataclass(frozen=True, kw_only=True)
class EnumOption:
    """Opção de um atributo do tipo enum."""

    key: str
    label: str


@dataclass(frozen=True, kw_only=True)
class AttributeDefinition:
    """Definição de um atributo de produto."""

    key: str
    label: str
    type: AttributeType
    unit: str | None = None
    options: tuple[EnumOption, ...] | None = None
    scope_type: ScopeType = ScopeType.GLOBAL
    scope_categories: tuple[str, ...] = field(default_factory=tuple)
    section: str = "geral"
    display_order: int = 0
    required: bool = False
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    max_length: int | None = None

    def applies_to_category(self, category_slug: str) -> bool:
        """Verifica se a definição se aplica à categoria dada."""
        if self.scope_type == ScopeType.GLOBAL:
            return True
        return category_slug in self.scope_categories

    def validate_value(self, value: Any) -> tuple[bool, str | None]:
        """Valida um valor contra esta definição.

        Returns:
            Tupla: (is_valid, error_message)
        """
        if value is None:
            return True, None

        if self.type == AttributeType.TEXT:
            return self._validate_text(value)
        if self.type == AttributeType.NUMBER:
            return self._validate_number(value)
        if self.type == AttributeType.ENUM:
            return self._validate_enum(value)
        if self.type == AttributeType.BOOLEAN:
            return self._validate_boolean(value)
        return False, f"Tipo de atributo desconhecido: {self.type}"

    def _validate_text(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, str):
            return False, f"Valor deve ser texto, recebido {type(value).__name__}"
        if self.max_length is not None and len(value) > self.max_length:
            return False, f"Texto excede {self.max_length} caracteres"
        return True, None

    def _validate_number(self, value: Any) -> tuple[bool, str | None]:
        try:
            num = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return False, f"Valor deve ser numérico, recebido {value!r}"
        if self.min_value is not None and num < self.min_value:
            return False, f"Valor deve ser >= {self.min_value}"
        if self.max_value is not None and num > self.max_value:
            return False, f"Valor deve ser <= {self.max_value}"
        return True, None

    def _validate_enum(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, str):
            return (
                False,
                f"Valor deve ser string (chave da opção), recebido {type(value).__name__}",
            )
        if self.options is None:
            return False, "Definição enum sem opções configuradas"
        valid_keys = {opt.key for opt in self.options}
        if value not in valid_keys:
            return False, f"Opção inválida: {value}. Válidas: {sorted(valid_keys)}"
        return True, None

    def _validate_boolean(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, bool):
            return False, f"Valor deve ser booleano, recebido {type(value).__name__}"
        return True, None


# ---------------------------------------------------------------------------
# Coleção de definições (registry)
# ---------------------------------------------------------------------------


@dataclass
class AttributeRegistry:
    """Registro de definições de atributos (carregado do seed/JSON)."""

    definitions: dict[str, AttributeDefinition] = field(default_factory=dict)

    def add(self, definition: AttributeDefinition) -> None:
        self.definitions[definition.key] = definition

    def get(self, key: str) -> AttributeDefinition | None:
        return self.definitions.get(key)

    def get_for_category(self, category_slug: str) -> list[AttributeDefinition]:
        """Retorna definições aplicáveis à categoria, ordenadas por section/display_order."""
        applicable = [d for d in self.definitions.values() if d.applies_to_category(category_slug)]
        applicable.sort(key=lambda d: (d.section, d.display_order, d.key))
        return applicable

    def get_required_for_category(self, category_slug: str) -> list[AttributeDefinition]:
        """Retorna definições obrigatórias para a categoria."""
        return [d for d in self.get_for_category(category_slug) if d.required]


# ---------------------------------------------------------------------------
# Validação e normalização de valores
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    """Erro de validação de atributos."""

    def __init__(self, message: str, key: str | None = None) -> None:
        super().__init__(message)
        self.key = key


def _discard_empty(value: Any) -> bool:
    """Verifica se o valor deve ser descartado (vazio)."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return bool(isinstance(value, list) and len(value) == 0)


def _normalize_value(value: Any, attr_type: AttributeType) -> Any:
    """Normaliza o valor conforme o tipo do atributo."""
    if attr_type == AttributeType.NUMBER:
        return Decimal(str(value))
    if attr_type == AttributeType.TEXT:
        return value.strip()
    return value


def normalize_and_validate_attributes(
    raw_attributes: dict[str, Any] | None,
    registry: AttributeRegistry,
    category_slug: str,
) -> dict[str, Any]:
    """Normaliza e valida atributos contra o registry.

    Regras:
    - Chave desconhecida → erro
    - Chave fora do escopo da categoria → erro
    - Tipo incorreto → erro
    - Valores vazios (None, "", whitespace, []) → descartados
    - Retorna dict apenas com chaves válidas e valores não vazios
    """
    if not raw_attributes:
        return {}

    normalized: dict[str, Any] = {}

    for key, value in raw_attributes.items():
        if _discard_empty(value):
            continue

        definition = registry.get(key)
        if definition is None:
            raise ValidationError(f"Atributo desconhecido: '{key}'", key=key)

        if not definition.applies_to_category(category_slug):
            raise ValidationError(
                f"Atributo '{key}' não se aplica à categoria '{category_slug}'",
                key=key,
            )

        is_valid, error = definition.validate_value(value)
        if not is_valid:
            raise ValidationError(f"Atributo '{key}': {error}", key=key)

        normalized[key] = _normalize_value(value, definition.type)

    return normalized


# ---------------------------------------------------------------------------
# Validação de campos obrigatórios do produto
# ---------------------------------------------------------------------------


def validate_product_required_fields(
    name: str | None,
    description: str | None,
    brand_id: str | None,
) -> list[str]:
    """Valida campos obrigatórios do produto.

    Returns:
        Lista de mensagens de erro (vazia se válido).
    """
    errors = []

    if not name or not name.strip():
        errors.append("Nome é obrigatório e não pode ser apenas espaços")
    elif len(name.strip()) > 200:
        errors.append("Nome excede 200 caracteres")

    if not description or not description.strip():
        errors.append("Descrição é obrigatória e não pode ser apenas espaços")
    elif len(description.strip()) > 2000:
        errors.append("Descrição excede 2000 caracteres")

    if not brand_id or not brand_id.strip():
        errors.append("Marca é obrigatória")

    return errors


# ---------------------------------------------------------------------------
# Carregamento do registry a partir de JSON (seed)
# ---------------------------------------------------------------------------


def _parse_scope(def_data: dict) -> tuple[ScopeType, tuple[str, ...]]:
    """Parseia o escopo do JSON para tipo e categorias."""
    scope = def_data.get("scope")
    if scope and scope != ["global"]:
        return ScopeType.CATEGORIES, tuple(scope)
    return ScopeType.GLOBAL, ()


def _parse_options(def_data: dict) -> tuple[EnumOption, ...] | None:
    """Parseia opções de enum do JSON."""
    options_data = def_data.get("options")
    if not options_data:
        return None
    return tuple(EnumOption(key=opt["key"], label=opt["label"]) for opt in options_data)


def _parse_decimal(value: Any) -> Decimal | None:
    """Parseia valor para Decimal se não None."""
    if value is None:
        return None
    return Decimal(str(value))


def load_registry_from_json(json_path: str) -> AttributeRegistry:
    """Carrega AttributeRegistry a partir de arquivo JSON do seed."""
    path = pathlib.Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    registry = AttributeRegistry()

    for def_data in data.get("definitions", []):
        scope_type, scope_categories = _parse_scope(def_data)
        options = _parse_options(def_data)

        definition = AttributeDefinition(
            key=def_data["key"],
            label=def_data["label"],
            type=AttributeType(def_data["type"]),
            unit=def_data.get("unit"),
            options=options,
            scope_type=scope_type,
            scope_categories=scope_categories,
            section=def_data.get("section", "geral"),
            display_order=def_data.get("display_order", 0),
            required=def_data.get("required", False),
            min_value=_parse_decimal(def_data.get("min_value")),
            max_value=_parse_decimal(def_data.get("max_value")),
            max_length=def_data.get("max_length"),
        )
        registry.add(definition)

    return registry
