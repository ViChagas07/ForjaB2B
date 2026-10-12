"""Manifesto de fotos para rascunhos de produtos (domínio puro, sem frameworks).

Este módulo define:
1. Função pura para converter nome de arquivo em nome de produto
2. Sugestão de categoria a partir do nome
3. Geração de SKU determinístico
4. Geração de preço determinístico dentro da faixa
5. Descrição gerada (1-2 frases, até 200 chars, tom neutro)
6. Geração de rascunhos a partir de arquivos

A validação e modelos Pydantic estão em `app.application.photo_manifest`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes e configuração
# ---------------------------------------------------------------------------

# Sufixos de cópia a remover
COPY_SUFFIXES = [
    r"\s*\(\d+\)\s*$",  # (1), (2), etc.
    r"\s*-\d+\s*$",  # -2, -3, etc.
    r"\s*copy\s*$",  # copy
    r"\s*cópia\s*$",  # cópia (pt-BR)
    r"\s*cópi a\s*$",  # cópia sem acento
]

# Preposições em minúsculas no título (português)
PORTUGUESE_PREPOSITIONS = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "na",
    "no",
    "nas",
    "nos",
    "por",
    "pelo",
    "pela",
    "pelos",
    "pelas",
    "para",
    "pra",
    "com",
    "sem",
    "sob",
    "sobre",
    "entre",
    "até",
    "após",
    "contra",
    "desde",
    "perante",
    "conforme",
    "segundo",
    "consoante",
    "e",
    "ou",
    "mas",
    "pois",
    "logo",
    "portanto",
}

# Padrão Pexels: pexels-<autor>-<número> ou pexels-photo-<número> ou pexels-<número>
# Usar três padrões separados para clareza
PEXELS_PHOTO_PATTERN = re.compile(r"^pexels-photo-(?P<number>\d+)$", re.IGNORECASE)
PEXELS_AUTHOR_PATTERN = re.compile(
    r"^pexels-(?P<author>[a-zA-Z0-9_-]+)-(?P<number>\d+)$", re.IGNORECASE
)
PEXELS_NUMBER_ONLY_PATTERN = re.compile(r"^pexels-(?P<number>\d+)$", re.IGNORECASE)

# Categorias válidas (slugs do seed)
VALID_CATEGORIES = {
    "epis",
    "protecao-cabeca",
    "protecao-visual",
    "protecao-maos",
    "protecao-respiratoria",
    "protecao-auditiva",
    "protecao-pes",
    "protecao-quedas",
    "maquinas-e-ferramentas",
    "ferramentas-eletricas",
    "maquinas-estacionarias",
}

# Marcas válidas (slugs do seed)
VALID_BRANDS = {
    "protec",
    "norton",
    "vulcano",
    "aegis",
    "guardian",
    "ferrum",
    "titan",
    "sentinel",
}

# Mapeamento determinístico categoria -> marca (para placeholders)
CATEGORY_TO_BRAND = {
    "epis": "protec",
    "protecao-cabeca": "protec",
    "protecao-visual": "aegis",
    "protecao-maos": "protec",
    "protecao-respiratoria": "protec",
    "protecao-auditiva": "aegis",
    "protecao-pes": "titan",
    "protecao-quedas": "vulcano",
    "maquinas-e-ferramentas": "norton",
    "ferramentas-eletricas": "vulcano",
    "maquinas-estacionarias": "titan",
}

# Faixas de preço por categoria (min, max) - baseadas no seed
CATEGORY_PRICE_RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "epis": (Decimal("10.00"), Decimal("60.00")),
    "protecao-cabeca": (Decimal("15.00"), Decimal("60.00")),
    "protecao-visual": (Decimal("15.00"), Decimal("31.00")),
    "protecao-maos": (Decimal("9.00"), Decimal("39.00")),
    "protecao-respiratoria": (Decimal("3.00"), Decimal("120.00")),
    "protecao-auditiva": (Decimal("3.00"), Decimal("35.00")),
    "protecao-pes": (Decimal("100.00"), Decimal("190.00")),
    "protecao-quedas": (Decimal("89.00"), Decimal("260.00")),
    "maquinas-e-ferramentas": (Decimal("200.00"), Decimal("1000.00")),
    "ferramentas-eletricas": (Decimal("279.00"), Decimal("899.00")),
    "maquinas-estacionarias": (Decimal("780.00"), Decimal("4590.00")),
}

# Termos proibidos na descrição
FORBIDDEN_TERMS = {
    "certificado",
    "certificação",
    "certificacao",
    "norma",
    "abnt",
    "iso",
    "desempenho",
    "potência",
    "potencia",
    "medida",
    "medidas",
    "material",
    "materiais",
    "garantia",
    "garantias",
    "watt",
    "volt",
    "ampere",
    "hp",
    "cv",
    "rpm",
    "mm",
    "cm",
    "kg",
    "l",
    "ml",
    "bar",
    "psi",
    "db",
    "hz",
}

# Padrões proibidos (regex) para casos como CA-12345
FORBIDDEN_PATTERNS = [
    r"\bca-\d+\b",  # CA-12345
]


# ---------------------------------------------------------------------------
# Enums e tipos auxiliares
# ---------------------------------------------------------------------------


class CategoryConfidence(StrEnum):
    ALTA = "alta"
    BAIXA = "baixa"


class NameSource(StrEnum):
    DERIVADO_ARQUIVO = "derivado do arquivo"
    MANUAL = "manual"


class DescriptionSource(StrEnum):
    GERADA = "gerada"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Modelo de dados simples (dataclass) para uso interno no domínio
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class DraftEntry:
    """Entrada de rascunho de produto (domínio puro, sem Pydantic)."""

    source_file: str
    sku: str
    name: str
    description: str
    category_slug: str
    brand: str
    list_price: Decimal
    needs_name: bool = False
    needs_review: bool = False
    brand_is_placeholder: bool = True
    price_is_demo: bool = True
    category_confidence: CategoryConfidence = CategoryConfidence.BAIXA
    name_source: NameSource = NameSource.DERIVADO_ARQUIVO
    description_source: DescriptionSource = DescriptionSource.GERADA
    source_url: str | None = None
    author: str | None = None
    license: str | None = None
    license_url: str | None = None
    downloaded_at: datetime | None = None
    attribution_text: str | None = None
    modifications: str | None = None
    inferred_from_filename: bool = False
    owner_verified: bool = False


@dataclass
class DraftManifest:
    """Manifesto de rascunhos (domínio puro)."""

    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    entries: list[DraftEntry] = field(default_factory=list)

    def add_entry(self, entry: DraftEntry) -> None:
        self.entries.append(entry)
        self.updated_at = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Função pura: nome de arquivo -> nome de produto
# ---------------------------------------------------------------------------


def filename_to_product_name(filename: str) -> tuple[str, bool, str | None, str | None]:
    """Converte nome de arquivo em nome de produto (função pura).

    Args:
        filename: Nome do arquivo (com ou sem extensão)

    Returns:
        Tupla: (nome_produto, needs_name, author_pexels, photo_number_pexels)
        - nome_produto: Nome formatado em português
        - needs_name: True se não foi possível inferir (padrão Pexels)
        - author_pexels: Autor se for padrão Pexels, senão None
        - photo_number_pexels: Número da foto Pexels, senão None
    """
    # Remover extensão
    name = Path(filename).stem

    # Verificar padrão Pexels photo (sem autor)
    pexels_photo_match = PEXELS_PHOTO_PATTERN.match(name)
    if pexels_photo_match:
        number = pexels_photo_match.group("number")
        return "", True, None, number

    # Verificar padrão Pexels com autor
    pexels_author_match = PEXELS_AUTHOR_PATTERN.match(name)
    if pexels_author_match:
        author = pexels_author_match.group("author")
        number = pexels_author_match.group("number")
        return "", True, author, number

    # Verificar padrão Pexels apenas número
    pexels_number_match = PEXELS_NUMBER_ONLY_PATTERN.match(name)
    if pexels_number_match:
        number = pexels_number_match.group("number")
        return "", True, None, number

    # Remover sufixos de cópia
    for pattern in COPY_SUFFIXES:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # Trocar separadores por espaço
    name = name.replace("-", " ").replace("_", " ")

    # Colapsar espaços múltiplos
    name = re.sub(r"\s+", " ", name).strip()

    # Título em português: capitalizar cada palavra exceto preposições
    words = name.split()
    titled_words = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i == 0 or lower not in PORTUGUESE_PREPOSITIONS:
            # Capitalizar primeira letra, manter resto como está (para acentos)
            titled_words.append(word[:1].upper() + word[1:] if word else "")
        else:
            titled_words.append(lower)

    product_name = " ".join(titled_words)

    # Corrigir acentos comuns que podem vir do nome do arquivo
    product_name = _fix_common_accents(product_name)

    return product_name, False, None, None


def _fix_common_accents(text: str) -> str:
    """Corrige acentos comuns em nomes derivados de arquivos."""
    # Mapeamento de palavras comuns sem acento -> com acento
    accent_map = {
        "oculos": "Óculos",
        "mascara": "Máscara",
        "mascaras": "Máscaras",
        "respirador": "Respirador",
        "respiradores": "Respiradores",
        "protetor": "Protetor",
        "protetores": "Protetores",
        "auricular": "Auricular",
        "auriculares": "Auriculares",
        "botina": "Botina",
        "botinas": "Botinas",
        "bota": "Bota",
        "botas": "Botas",
        "capacete": "Capacete",
        "capacetes": "Capacetes",
        "luva": "Luva",
        "luvas": "Luvas",
        "colete": "Colete",
        "coletes": "Coletes",
        "furadeira": "Furadeira",
        "furadeiras": "Furadeiras",
        "esmerilhadeira": "Esmerilhadeira",
        "esmerilhadeiras": "Esmerilhadeiras",
        "serra": "Serra",
        "serras": "Serras",
        "parafusadeira": "Parafusadeira",
        "parafusadeiras": "Parafusadeiras",
        "kit": "Kit",
        "kits": "Kits",
        "para": "para",
        "de": "de",
        "da": "da",
        "do": "do",
        "das": "das",
        "dos": "dos",
        "em": "em",
        "na": "na",
        "no": "no",
        "com": "com",
        "obra": "Obra",
        "protecao": "Proteção",
        "proteção": "Proteção",
        "seguranca": "Segurança",
        "segurança": "Segurança",
        "trabalho": "Trabalho",
        "industrial": "Industrial",
        "profissional": "Profissional",
    }

    words = text.split()
    corrected = []
    for word in words:
        lower = word.lower()
        if lower in accent_map:
            corrected.append(accent_map[lower])
        else:
            # Tentar normalizar via unicode
            normalized = unicodedata.normalize("NFC", word)
            corrected.append(normalized)

    return " ".join(corrected)


# ---------------------------------------------------------------------------
# Sugestão de categoria a partir do nome
# ---------------------------------------------------------------------------


def suggest_category(product_name: str) -> tuple[str, CategoryConfidence]:
    """Sugere categoria baseada no nome do produto (heurística simples).

    Returns:
        Tupla: (category_slug, confidence)
    """
    name_lower = product_name.lower()

    # Mapeamento de palavras-chave para categoria
    category_keywords: dict[str, list[str]] = {
        "protecao-cabeca": ["capacete"],
        "protecao-visual": ["óculos", "oculos"],
        "protecao-maos": ["luva", "luvas"],
        "protecao-respiratoria": [
            "máscara",
            "mascara",
            "respirador",
            "máscaras",
            "mascaras",
        ],
        "protecao-auditiva": ["protetor", "abafador", "auricular", "plug"],
        "protecao-pes": [
            "botina",
            "bota",
            "botas",
            "sapato",
            "calçado",
            "calcado",
        ],
        "protecao-quedas": [
            "cinto",
            "talabarte",
            "cinturão",
            "cinturao",
            "trava",
            "queda",
        ],
        "ferramentas-eletricas": [
            "furadeira",
            "esmerilhadeira",
            "serra",
            "parafusadeira",
            "retífica",
            "retifica",
            "politriz",
        ],
        "maquinas-estacionarias": [
            "compressor",
            "prensa",
            "torno",
            "bomba",
            "maquina",
            "máquina",
            "bancada",
        ],
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in name_lower:
                return category, CategoryConfidence.ALTA

    # Se não encontrou, default para EPIs genérico
    return "epis", CategoryConfidence.BAIXA


# ---------------------------------------------------------------------------
# Geração de SKU determinístico
# ---------------------------------------------------------------------------


def generate_sku(source_file: str, category_slug: str) -> str:
    """Gera SKU determinístico a partir do arquivo e categoria.

    Formato: PREFIXO-CAT-###
    """
    # Prefixo por categoria
    prefix_map = {
        "protecao-cabeca": "CAP",
        "protecao-visual": "OCV",
        "protecao-maos": "LUV",
        "protecao-respiratoria": "RES",
        "protecao-auditiva": "AUD",
        "protecao-pes": "BOT",
        "protecao-quedas": "QUE",
        "ferramentas-eletricas": "FUR",
        "maquinas-estacionarias": "MAQ",
        "epis": "EPI",
        "maquinas-e-ferramentas": "MAQ",
    }

    prefix = prefix_map.get(category_slug, "EPI")
    cat_code = prefix[:3]

    # Hash determinístico do nome do arquivo para número sequencial
    file_hash = hash(source_file)
    number = abs(file_hash) % 900 + 100  # 100-999

    return f"EPI-{cat_code}-{number:03d}"


# ---------------------------------------------------------------------------
# Preço determinístico dentro da faixa
# ---------------------------------------------------------------------------


def generate_price(category_slug: str, source_file: str) -> Decimal:
    """Gera preço determinístico dentro da faixa da categoria."""
    default_range = (Decimal("10.00"), Decimal("1000.00"))
    min_price, max_price = CATEGORY_PRICE_RANGES.get(category_slug, default_range)

    # Hash do arquivo para determinismo
    file_hash = hash(source_file)
    # Normalizar para 0-1
    normalized = (abs(file_hash) % 10000) / 10000.0

    # Interpolar na faixa
    price_range = max_price - min_price
    price = min_price + (price_range * Decimal(str(normalized)))

    # Arredondar como varejo (duas casas, .90 ou .50 ou .00)
    # Usar centavos para arredondamento comercial
    cents = int((price * 100).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
    rounded_cents = (cents // 10) * 10  # Múltiplo de 10 centavos
    if rounded_cents == 0:
        rounded_cents = 10

    return Decimal(rounded_cents) / 100


# ---------------------------------------------------------------------------
# Descrição gerada (1-2 frases, até 200 chars, tom neutro)
# ---------------------------------------------------------------------------


def generate_description(product_name: str, category_slug: str) -> str:
    """Gera descrição neutra de catálogo (1-2 frases, até 200 chars)."""
    # Templates por categoria
    templates: dict[str, str] = {
        "protecao-cabeca": (
            "{name} para proteção da cabeça em ambientes industriais e de construção."
        ),
        "protecao-visual": ("{name} para proteção visual contra partículas e radiação."),
        "protecao-maos": ("{name} para proteção das mãos em atividades de risco mecânico."),
        "protecao-respiratoria": ("{name} para proteção respiratória contra poeiras e vapores."),
        "protecao-auditiva": ("{name} para proteção auditiva contra ruídos elevados."),
        "protecao-pes": ("{name} para proteção dos pés em ambientes industriais."),
        "protecao-quedas": ("{name} para proteção contra quedas em trabalho em altura."),
        "ferramentas-eletricas": (
            "{name} para aplicações profissionais em construção e indústria."
        ),
        "maquinas-estacionarias": "{name} para uso industrial e oficinal.",
        "epis": "{name} para proteção individual em ambiente de trabalho.",
        "maquinas-e-ferramentas": "{name} para aplicações profissionais.",
    }

    template = templates.get(category_slug, templates["epis"])
    description = template.format(name=product_name)

    # Garantir limite de 200 chars
    if len(description) > 200:
        description = description[:197] + "..."

    return description


# ---------------------------------------------------------------------------
# Geração de rascunhos a partir de arquivos
# ---------------------------------------------------------------------------


@dataclass
class DraftConfig:
    """Configuração para geração de rascunhos."""

    input_dir: Path
    manifest_path: Path


def generate_drafts(config: DraftConfig) -> DraftManifest:
    """Gera rascunhos de produtos a partir dos arquivos na pasta de entrada."""
    manifest = DraftManifest()

    if not config.input_dir.exists():
        return manifest

    # Extensões de imagem suportadas
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".avif"}

    files = sorted(
        [
            f
            for f in config.input_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]
    )

    for file_path in files:
        entry = create_draft_entry(file_path)
        manifest.add_entry(entry)

    return manifest


def create_draft_entry(file_path: Path) -> DraftEntry:
    """Cria uma entrada de rascunho para um arquivo."""
    filename = file_path.name

    # Nome do produto
    product_name, needs_name, pexels_author, pexels_number = filename_to_product_name(filename)

    # Categoria
    if needs_name:
        category_slug = "epis"
        category_confidence = CategoryConfidence.BAIXA
        needs_review = True
    else:
        category_slug, category_confidence = suggest_category(product_name)
        needs_review = category_confidence == CategoryConfidence.BAIXA

    # Marca (placeholder determinístico por categoria)
    brand_slug = CATEGORY_TO_BRAND.get(category_slug, "protec")

    # SKU
    sku = generate_sku(filename, category_slug)

    # Preço
    list_price = generate_price(category_slug, filename)

    # Descrição
    if needs_name:
        description = "Produto a identificar e descrever pelo responsável."
    else:
        description = generate_description(product_name, category_slug)

    # Créditos Pexels
    source_url = None
    author = None
    license_val = None
    license_url = None
    inferred_from_filename = False

    if pexels_author and pexels_number:
        inferred_from_filename = True
        author = pexels_author.replace("-", " ").title()
        source_url = f"https://www.pexels.com/photo/{pexels_number}/"
        license_val = "Pexels License"
        license_url = "https://www.pexels.com/license/"

    # Nome a usar (se needs_name, usar placeholder)
    final_name = product_name if not needs_name else "Produto a identificar"

    return DraftEntry(
        source_file=filename,
        sku=sku,
        name=final_name,
        description=description,
        category_slug=category_slug,
        brand=brand_slug,
        list_price=list_price,
        needs_name=needs_name,
        needs_review=needs_review,
        brand_is_placeholder=True,
        price_is_demo=True,
        category_confidence=category_confidence,
        name_source=(NameSource.DERIVADO_ARQUIVO if not needs_name else NameSource.MANUAL),
        description_source=DescriptionSource.GERADA,
        source_url=source_url,
        author=author,
        license=license_val,
        license_url=license_url,
        downloaded_at=datetime.now(UTC),
        attribution_text=None,
        modifications=None,
        inferred_from_filename=inferred_from_filename,
        owner_verified=False,
    )
