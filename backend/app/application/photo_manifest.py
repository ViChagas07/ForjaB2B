"""Manifesto de fotos para rascunhos de produtos - camada de aplicação (Pydantic v2).

Esta camada contém os modelos Pydantic para serialização/validação do manifesto.
A lógica pura de domínio está em `app.domain.photo_manifest`.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.photo_manifest import (
    CATEGORY_PRICE_RANGES,
    FORBIDDEN_PATTERNS,
    FORBIDDEN_TERMS,
    VALID_BRANDS,
    VALID_CATEGORIES,
    CategoryConfidence,
    DescriptionSource,
    DraftConfig,
    NameSource,
    create_draft_entry,
    generate_drafts,
)

# ---------------------------------------------------------------------------
# Modelos Pydantic do Manifesto
# ---------------------------------------------------------------------------


class ManifestEntry(BaseModel):
    """Uma entrada do manifesto de fotos para rascunho de produto."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Identificação da fonte
    source_file: str = Field(min_length=1, max_length=255)

    # Produto (campos principais)
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=200)
    category_slug: str = Field(min_length=1, max_length=150)
    brand: str = Field(min_length=1, max_length=150)
    list_price: Decimal = Field(gt=0, decimal_places=2)

    # Flags de controle
    needs_name: bool = False
    needs_review: bool = False
    brand_is_placeholder: bool = True
    price_is_demo: bool = True
    category_confidence: CategoryConfidence = CategoryConfidence.BAIXA
    name_source: NameSource = NameSource.DERIVADO_ARQUIVO
    description_source: DescriptionSource = DescriptionSource.GERADA

    # Créditos e licença
    source_url: str | None = None
    author: str | None = None
    license: str | None = None
    license_url: str | None = None
    downloaded_at: datetime | None = None
    attribution_text: str | None = None
    modifications: str | None = None
    inferred_from_filename: bool = False

    # Verificação do responsável
    owner_verified: bool = False

    @field_validator("category_slug")
    @classmethod
    def validate_category_slug(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category_slug '{v}' não é uma categoria válida")
        return v

    @field_validator("brand")
    @classmethod
    def validate_brand(cls, v: str) -> str:
        if v not in VALID_BRANDS:
            raise ValueError(f"brand '{v}' não é uma marca válida do seed")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("description excede 200 caracteres")
        # Verificar termos proibidos (case-insensitive, palavra inteira)
        # Normalizar para remover acentos para comparação
        import unicodedata

        normalized_v = (
            unicodedata.normalize("NFKD", v.lower()).encode("ascii", "ignore").decode("ascii")
        )
        for term in FORBIDDEN_TERMS:
            # Normalizar termo também
            normalized_term = (
                unicodedata.normalize("NFKD", term.lower())
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            # Usar word boundary no texto normalizado
            import re

            pattern = rf"\b{re.escape(normalized_term)}\b"
            if re.search(pattern, normalized_v):
                raise ValueError(f"description contém termo proibido: '{term}'")
        # Verificar padrões proibidos (regex)
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, v.lower()):
                raise ValueError(f"description contém padrão proibido: '{pattern}'")
        return v

    @field_validator("sku")
    @classmethod
    def validate_sku_format(cls, v: str) -> str:
        # SKU deve seguir padrão: PREFIXO-### ou PREFIXO-####
        import re

        if not re.match(r"^[A-Z]{2,4}-[A-Z]{2,3}-\d{3,4}$", v):
            raise ValueError(f"SKU '{v}' não segue o padrão esperado (ex.: EPI-CAP-001)")
        return v

    def is_publishable(self) -> bool:
        """Verifica se a entrada está pronta para publicação.

        Critérios: owner_verified=True, needs_name=False, créditos completos.
        """
        if not self.owner_verified:
            return False
        if self.needs_name:
            return False
        # Créditos mínimos: source_url ou author preenchidos
        return bool(self.source_url or self.author)


class PhotoManifest(BaseModel):
    """Manifesto completo de fotos para rascunhos de produtos."""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: list[ManifestEntry] = Field(default_factory=list)

    def add_entry(self, entry: ManifestEntry) -> None:
        self.entries.append(entry)
        self.updated_at = datetime.now(UTC)

    def get_publishable_entries(self) -> list[ManifestEntry]:
        return [e for e in self.entries if e.is_publishable()]

    def get_pending_entries(self) -> list[ManifestEntry]:
        return [e for e in self.entries if not e.is_publishable()]


# ---------------------------------------------------------------------------
# Validador do manifesto
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel):
    """Resultado da validação."""

    model_config = ConfigDict(extra="forbid", strict=True)

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _validate_entry(entry: ManifestEntry, index: int) -> tuple[list[str], list[str]]:
    """Valida uma única entrada do manifesto.

    Returns:
        Tupla: (errors, warnings)
    """
    errors = []
    warnings = []

    # Validar via Pydantic (já faz a maior parte)
    try:
        ManifestEntry.model_validate(entry.model_dump())
    except Exception as e:  # noqa: BLE001
        errors.append(f"Entrada {index} ({entry.source_file}): {e}")

    # Verificações adicionais
    if entry.owner_verified:
        if entry.needs_name:
            errors.append(
                f"Entrada {index} ({entry.source_file}): owner_verified=True mas needs_name=True"
            )
        if not entry.source_url and not entry.author:
            warnings.append(
                f"Entrada {index} ({entry.source_file}): "
                "owner_verified=True mas créditos incompletos"
            )
    else:
        # Não publicável - registrar como warning para visibilidade
        reasons = []
        if not entry.owner_verified:
            reasons.append("owner_verified=False")
        if entry.needs_name:
            reasons.append("needs_name=True")
        if not entry.source_url and not entry.author:
            reasons.append("créditos incompletos")
        warnings.append(
            f"Entrada {index} ({entry.source_file}): não publicável ({', '.join(reasons)})"
        )

    return errors, warnings


def validate_manifest(manifest: PhotoManifest) -> ValidationResult:
    """Valida o manifesto completo.

    Regras:
    - Entrada deve ter sku, name, description, category_slug válida, brand existente
    - Descrição não pode exceder 200 chars ou conter termos proibidos
    - Entrada com owner_verified=False, needs_name=True ou créditos incompletos
      = "não publicável"
    """
    errors: list[str] = []
    warnings: list[str] = []

    for i, entry in enumerate(manifest.entries):
        entry_errors, entry_warnings = _validate_entry(entry, i)
        errors.extend(entry_errors)
        warnings.extend(entry_warnings)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Utilitários de serialização
# ---------------------------------------------------------------------------


def save_manifest(manifest: PhotoManifest, path: Path) -> None:
    """Salva manifesto em JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def load_manifest(path: Path) -> PhotoManifest:
    """Carrega manifesto de JSON."""
    if not path.exists():
        return PhotoManifest()
    return PhotoManifest.model_validate_json(path.read_text(encoding="utf-8"))


def create_empty_manifest_template(path: Path) -> None:
    """Cria um modelo vazio do manifesto com instruções."""
    template = {
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "entries": [],
        "_instructions": {
            "description": (
                "Manifesto de rascunhos de produtos a partir de fotos. "
                "Preencha uma entrada por foto."
            ),
            "fields": {
                "source_file": "Nome do arquivo original (ex.: 'capacete.jpg')",
                "sku": "SKU seguindo convenção (ex.: 'EPI-CAP-001')",
                "name": "Nome do produto em pt-BR (ex.: 'Capacete de Segurança')",
                "description": (
                    "Descrição neutra 1-2 frases, máx 200 chars, sem termos técnicos proibidos"
                ),
                "category_slug": "Slug da categoria existente (ver VALID_CATEGORIES)",
                "brand": "Slug da marca fictícia existente (ver VALID_BRANDS)",
                "list_price": "Preço de lista em BRL (Decimal, ex.: 24.90)",
                "needs_name": "True se nome não pôde ser inferido (padrão Pexels)",
                "needs_review": ("True se categoria/preço/marca precisam revisão humana"),
                "brand_is_placeholder": "True se marca é placeholder do seed",
                "price_is_demo": "True se preço é de demonstração",
                "category_confidence": "'alta' ou 'baixa'",
                "name_source": "'derivado do arquivo' ou 'manual'",
                "description_source": "'gerada' ou 'manual'",
                "source_url": "URL de origem da foto (ex.: Pexels)",
                "author": "Autor da foto",
                "license": "Licença sugerida (ex.: 'Pexels License')",
                "license_url": "URL da licença",
                "downloaded_at": "Data de download (ISO 8601)",
                "attribution_text": "Texto de atribuição completo",
                "modifications": "Descrição de modificações feitas na imagem",
                "inferred_from_filename": ("True se créditos foram inferidos do nome do arquivo"),
                "owner_verified": (
                    "True APENAS após responsável conferir licença, "
                    "rostos, logos, nome, descrição, categoria, marca, preço"
                ),
            },
            "publishable_criteria": (
                "owner_verified=True E needs_name=False E (source_url OU author preenchidos)"
            ),
            "valid_categories": sorted(list(VALID_CATEGORIES)),
            "valid_brands": sorted(list(VALID_BRANDS)),
            "category_price_ranges": {
                k: [str(v[0]), str(v[1])] for k, v in CATEGORY_PRICE_RANGES.items()
            },
            "forbidden_terms_in_description": sorted(list(FORBIDDEN_TERMS)),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Função de conveniência para criar rascunhos usando a lógica de domínio
# ---------------------------------------------------------------------------


def create_draft_entry_from_file(file_path: Path) -> ManifestEntry:
    """Cria uma entrada de rascunho para um arquivo usando lógica de domínio."""
    # Usar a função de domínio para criar a entrada base
    domain_entry = create_draft_entry(file_path)

    # Converter para modelo Pydantic da aplicação
    return ManifestEntry(**dataclasses.asdict(domain_entry))


def generate_drafts_from_dir(input_dir: Path) -> PhotoManifest:
    """Gera rascunhos de produtos a partir dos arquivos na pasta de entrada."""
    config = DraftConfig(input_dir=input_dir, manifest_path=Path(""))
    domain_manifest = generate_drafts(config)

    # Converter para modelo Pydantic da aplicação
    manifest = PhotoManifest(
        version=domain_manifest.version,
        created_at=domain_manifest.created_at,
        updated_at=domain_manifest.updated_at,
    )
    for entry in domain_manifest.entries:
        manifest.add_entry(ManifestEntry(**dataclasses.asdict(entry)))

    return manifest
