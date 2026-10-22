"""Modelos Pydantic para atributos de produto (camada de aplicação).

Esta camada expõe os modelos para uso na API de administração (Fase 9-b).
A lógica de validação pura reside em `app.domain.product_attributes`.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.product_attributes import (
    AttributeDefinition,
    AttributeRegistry,
    AttributeType,
    EnumOption,
    ScopeType,
    load_registry_from_json,
    normalize_and_validate_attributes,
    validate_product_required_fields,
)

# ---------------------------------------------------------------------------
# Schemas Pydantic para API
# ---------------------------------------------------------------------------


class EnumOptionSchema(BaseModel):
    """Opção de enum para a API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)


class AttributeDefinitionSchema(BaseModel):
    """Definição de atributo para a API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    type: AttributeType
    unit: str | None = Field(default=None, max_length=20)
    options: list[EnumOptionSchema] | None = None
    scope: list[str] = Field(default_factory=list)
    section: str = Field(default="geral", max_length=50)
    display_order: int = Field(default=0, ge=0)
    required: bool = False
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    max_length: int | None = Field(default=None, gt=0)

    @field_validator("options", mode="before")
    @classmethod
    def _validate_options(cls, v: list[dict[str, Any]] | None) -> list[EnumOptionSchema] | None:
        if v is None:
            return None
        return [EnumOptionSchema(**opt) for opt in v]

    def to_domain(self) -> AttributeDefinition:
        """Converte para definição de domínio."""
        options = None
        if self.options:
            options = tuple(EnumOption(key=opt.key, label=opt.label) for opt in self.options)

        scope_type = ScopeType.GLOBAL
        scope_categories: tuple[str, ...] = ()
        if self.scope and self.scope != ["global"]:
            scope_type = ScopeType.CATEGORIES
            scope_categories = tuple(self.scope)

        return AttributeDefinition(
            key=self.key,
            label=self.label,
            type=self.type,
            unit=self.unit,
            options=options,
            scope_type=scope_type,
            scope_categories=scope_categories,
            section=self.section,
            display_order=self.display_order,
            required=self.required,
            min_value=self.min_value,
            max_value=self.max_value,
            max_length=self.max_length,
        )


class AttributeDefinitionsPayload(BaseModel):
    """Payload para criar/atualizar múltiplas definições."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    definitions: list[AttributeDefinitionSchema] = Field(min_length=1)


class ProductAttributesPayload(BaseModel):
    """Payload de atributos de um produto para a API."""

    model_config = ConfigDict(extra="forbid")

    attributes: dict[str, Any] = Field(default_factory=dict)


class ProductRequiredFieldsPayload(BaseModel):
    """Campos obrigatórios do produto para a API."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    brand_id: str = Field(min_length=36, max_length=36)

    @field_validator("name", "description")
    @classmethod
    def _not_empty_or_spaces(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Campo não pode ser vazio ou apenas espaços")
        return v.strip()


# ---------------------------------------------------------------------------
# Serviços de aplicação
# ---------------------------------------------------------------------------


class AttributeService:
    """Serviço de aplicação para atributos de produto."""

    def __init__(self, registry: AttributeRegistry | None = None) -> None:
        self._registry = registry or AttributeRegistry()

    @property
    def registry(self) -> AttributeRegistry:
        return self._registry

    def load_from_json(self, json_path: str) -> None:
        """Carrega definições a partir de arquivo JSON (seed)."""
        loaded = load_registry_from_json(json_path)
        self._registry = loaded

    def get_definitions_for_category(self, category_slug: str) -> list[AttributeDefinitionSchema]:
        """Retorna definições aplicáveis à categoria como schemas da API."""
        domain_defs = self._registry.get_for_category(category_slug)
        return [AttributeDefinitionSchema.model_validate(d.__dict__) for d in domain_defs]

    def get_required_definitions_for_category(
        self, category_slug: str
    ) -> list[AttributeDefinitionSchema]:
        """Retorna definições obrigatórias para a categoria."""
        domain_defs = self._registry.get_required_for_category(category_slug)
        return [AttributeDefinitionSchema.model_validate(d.__dict__) for d in domain_defs]

    def validate_and_normalize_attributes(
        self,
        raw_attributes: dict[str, Any],
        category_slug: str,
    ) -> dict[str, Any]:
        """Valida e normaliza atributos para persistência.

        Raises:
            ValidationError: se houver erro de validação
        """
        return normalize_and_validate_attributes(raw_attributes, self._registry, category_slug)

    def validate_product_required_fields(
        self,
        name: str,
        description: str,
        brand_id: str,
    ) -> list[str]:
        """Valida campos obrigatórios do produto.

        Returns:
            Lista de erros (vazia se válido).
        """
        return validate_product_required_fields(name, description, brand_id)


# ---------------------------------------------------------------------------
# Utilitários de seed
# ---------------------------------------------------------------------------

DEFAULT_ATTRIBUTES_JSON = (
    '{"version": 1,'
    '"definitions": ['
    '{"key": "modelo", "label": "Modelo", "type": "text", '
    '"scope": ["global"], "section": "identificacao", '
    '"display_order": 10, "max_length": 100},'
    '{"key": "cor", "label": "Cor", "type": "text", '
    '"scope": ["global"], "section": "identificacao", '
    '"display_order": 20, "max_length": 50},'
    '{"key": "tamanho", "label": "Tamanho", "type": "text", '
    '"scope": ["global"], "section": "identificacao", '
    '"display_order": 30, "max_length": 50},'
    '{"key": "material", "label": "Material", "type": "text", '
    '"scope": ["global"], "section": "tecnico", '
    '"display_order": 10, "max_length": 100},'
    '{"key": "peso_kg", "label": "Peso (kg)", "type": "number", '
    '"unit": "kg", "scope": ["global"], "section": "tecnico", '
    '"display_order": 20, "min_value": 0.001, "max_value": 10000},'
    '{"key": "unidade_venda", "label": "Unidade de Venda", "type": "text", '
    '"scope": ["global"], "section": "comercial", '
    '"display_order": 10, "max_length": 20},'
    '{"key": "tamanho_luvas", "label": "Tamanho (Luvas)", "type": "enum", '
    '"options": [{"key": "P", "label": "P"}, {"key": "M", "label": "M"}, '
    '{"key": "G", "label": "G"}, {"key": "GG", "label": "GG"}], '
    '"scope": ["protecao-maos"], "section": "ajuste", "display_order": 10},'
    '{"key": "tamanho_botas", "label": "Tamanho (Botas)", "type": "enum", '
    '"options": [{"key": "35", "label": "35"}, {"key": "36", "label": "36"}, '
    '{"key": "37", "label": "37"}, {"key": "38", "label": "38"}, '
    '{"key": "39", "label": "39"}, {"key": "40", "label": "40"}, '
    '{"key": "41", "label": "41"}, {"key": "42", "label": "42"}, '
    '{"key": "43", "label": "43"}, {"key": "44", "label": "44"}, '
    '{"key": "45", "label": "45"}, {"key": "46", "label": "46"}], '
    '"scope": ["protecao-pes"], "section": "ajuste", "display_order": 10},'
    '{"key": "cor_capacete", "label": "Cor (Capacete)", "type": "enum", '
    '"options": [{"key": "branco", "label": "Branco"}, '
    '{"key": "amarelo", "label": "Amarelo"}, {"key": "azul", "label": "Azul"}, '
    '{"key": "vermelho", "label": "Vermelho"}, {"key": "verde", "label": "Verde"}, '
    '{"key": "laranja", "label": "Laranja"}, {"key": "preto", "label": "Preto"}], '
    '"scope": ["protecao-cabeca"], "section": "identificacao", '
    '"display_order": 5},'
    '{"key": "cor_coleta", "label": "Cor (Colete)", "type": "enum", '
    '"options": [{"key": "amarelo", "label": "Amarelo"}, '
    '{"key": "laranja", "label": "Laranja"}, {"key": "verde", "label": "Verde"}], '
    '"scope": ["epis"], "section": "identificacao", "display_order": 5},'
    '{"key": "potencia_w", "label": "Potência (W)", "type": "number", '
    '"unit": "W", "scope": ["ferramentas-eletricas", "maquinas-estacionarias"], '
    '"section": "tecnico", "display_order": 10, '
    '"min_value": 10, "max_value": 50000},'
    '{"key": "tensao_v", "label": "Tensão (V)", "type": "enum", '
    '"options": [{"key": "110", "label": "110V"}, '
    '{"key": "220", "label": "220V"}, {"key": "bivolt", "label": "Bivolt"}], '
    '"scope": ["ferramentas-eletricas", "maquinas-estacionarias"], '
    '"section": "tecnico", "display_order": 20},'
    '{"key": "ca", "label": "CA (Certificado de Aprovação)", "type": "text", '
    '"scope": ["epis"], "section": "conformidade", '
    '"display_order": 10, "max_length": 64}'
    "]"
    "}"
)


def create_default_attributes_json(path: Path) -> None:
    """Cria arquivo JSON padrão com as definições de atributos."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_ATTRIBUTES_JSON.strip(), encoding="utf-8")


def load_default_registry() -> AttributeRegistry:
    """Carrega registry com definições padrão (do JSON embutido)."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(DEFAULT_ATTRIBUTES_JSON.strip())
        temp_path = f.name

    try:
        return load_registry_from_json(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)
