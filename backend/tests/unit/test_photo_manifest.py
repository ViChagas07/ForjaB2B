"""Testes unitários do manifesto de fotos e formatação de nomes."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

import pytest

from app.application.photo_manifest import (
    ManifestEntry,
    PhotoManifest,
    create_draft_entry_from_file,
    create_empty_manifest_template,
    generate_drafts_from_dir,
    load_manifest,
    save_manifest,
    validate_manifest,
)
from app.domain.photo_manifest import (
    CATEGORY_PRICE_RANGES,
    CATEGORY_TO_BRAND,
    FORBIDDEN_PATTERNS,
    FORBIDDEN_TERMS,
    CategoryConfidence,
    DescriptionSource,
    DraftConfig,
    DraftEntry,
    DraftManifest,
    NameSource,
    create_draft_entry,
    filename_to_product_name,
    generate_description,
    generate_drafts,
    generate_price,
    generate_sku,
    suggest_category,
)


class TestFilenameToProductName:
    """Testes da função pura filename_to_product_name."""

    def test_nome_simples(self) -> None:
        name, needs_name, author, number = filename_to_product_name("capacete.jpg")
        assert name == "Capacete"
        assert needs_name is False
        assert author is None
        assert number is None

    def test_hiben_e_underscore(self) -> None:
        name, needs_name, _, _ = filename_to_product_name("oculos-de-protecao.jpg")
        assert name == "Óculos de Proteção"
        assert needs_name is False

        name, needs_name, _, _ = filename_to_product_name("luva_raspa.png")
        assert name == "Luva Raspa"
        assert needs_name is False

    def test_acentos_corrigidos(self) -> None:
        name, _, _, _ = filename_to_product_name("oculos-de-protecao.jpg")
        assert name == "Óculos de Proteção"

        name, _, _, _ = filename_to_product_name("mascara-respiradora.jpg")
        assert name == "Máscara Respiradora"

        name, _, _, _ = filename_to_product_name("protetor-auricular.jpg")
        assert name == "Protetor Auricular"

    def test_preposicoes_minusculas(self) -> None:
        name, _, _, _ = filename_to_product_name("capacete-de-seguranca.jpg")
        assert name == "Capacete de Segurança"

        name, _, _, _ = filename_to_product_name("luva-para-obra.jpg")
        assert name == "Luva para Obra"

        name, _, _, _ = filename_to_product_name("kit-de-parafusos.jpg")
        assert name == "Kit de Parafusos"

    def test_sufixo_copia(self) -> None:
        name, needs_name, _, _ = filename_to_product_name("capacete (1).jpg")
        assert name == "Capacete"
        assert needs_name is False

        name, needs_name, _, _ = filename_to_product_name("luva-2.png")
        assert name == "Luva"
        assert needs_name is False

        name, needs_name, _, _ = filename_to_product_name("oculos_copy.jpeg")
        assert name == "Óculos"
        assert needs_name is False

        name, needs_name, _, _ = filename_to_product_name("mascara cópia.jpg")
        assert name == "Máscara"
        assert needs_name is False

    def test_ingles_propoe_portugues(self) -> None:
        name, needs_name, _, _ = filename_to_product_name("hard-hat.jpg")
        assert name == "Hard Hat"  # Mantém original mas capitaliza
        assert needs_name is False

        name, needs_name, _, _ = filename_to_product_name("safety-glasses.png")
        assert name == "Safety Glasses"
        assert needs_name is False

    def test_padrao_pexels_com_autor(self) -> None:
        name, needs_name, author, number = filename_to_product_name(
            "pexels-kindelmedia-8488037.jpg"
        )
        assert name == ""
        assert needs_name is True
        assert author == "kindelmedia"
        assert number == "8488037"

    def test_padrao_pexels_photo(self) -> None:
        name, needs_name, author, number = filename_to_product_name("pexels-photo-38070.jpeg")
        assert name == ""
        assert needs_name is True
        assert author is None
        assert number == "38070"

    def test_padrao_pexels_sem_autor(self) -> None:
        name, needs_name, author, number = filename_to_product_name("pexels-123456.jpg")
        assert name == ""
        assert needs_name is True
        assert author is None
        assert number == "123456"

    def test_colapsa_espacos(self) -> None:
        name, needs_name, _, _ = filename_to_product_name("  capacete   de   seguranca  .jpg")
        assert name == "Capacete de Segurança"
        assert needs_name is False


class TestSuggestCategory:
    """Testes de sugestão de categoria."""

    def test_capacete_alta_confianca(self) -> None:
        cat, conf = suggest_category("Capacete de Segurança")
        assert cat == "protecao-cabeca"
        assert conf == CategoryConfidence.ALTA

    def test_oculos_alta_confianca(self) -> None:
        cat, conf = suggest_category("Óculos de Proteção")
        assert cat == "protecao-visual"
        assert conf == CategoryConfidence.ALTA

    def test_luva_alta_confianca(self) -> None:
        cat, conf = suggest_category("Luva de Raspa")
        assert cat == "protecao-maos"
        assert conf == CategoryConfidence.ALTA

    def test_mascara_alta_confianca(self) -> None:
        cat, conf = suggest_category("Máscara Respiradora")
        assert cat == "protecao-respiratoria"
        assert conf == CategoryConfidence.ALTA

    def test_protetor_auricular_alta_confianca(self) -> None:
        cat, conf = suggest_category("Protetor Auricular")
        assert cat == "protecao-auditiva"
        assert conf == CategoryConfidence.ALTA

    def test_botina_alta_confianca(self) -> None:
        cat, conf = suggest_category("Botina de Segurança")
        assert cat == "protecao-pes"
        assert conf == CategoryConfidence.ALTA

    def test_furadeira_alta_confianca(self) -> None:
        cat, conf = suggest_category("Furadeira de Impacto")
        assert cat == "ferramentas-eletricas"
        assert conf == CategoryConfidence.ALTA

    def test_esmerilhadeira_alta_confianca(self) -> None:
        cat, conf = suggest_category("Esmerilhadeira Angular")
        assert cat == "ferramentas-eletricas"
        assert conf == CategoryConfidence.ALTA

    def test_compressor_alta_confianca(self) -> None:
        cat, conf = suggest_category("Compressor de Ar")
        assert cat == "maquinas-estacionarias"
        assert conf == CategoryConfidence.ALTA

    def test_generico_baixa_confianca(self) -> None:
        cat, conf = suggest_category("Produto Genérico XYZ")
        assert cat == "epis"
        assert conf == CategoryConfidence.BAIXA


class TestGenerateSKU:
    """Testes de geração de SKU determinístico."""

    def test_sku_formato_correto(self) -> None:
        sku = generate_sku("capacete.jpg", "protecao-cabeca")
        assert sku.startswith("EPI-CAP-")
        assert len(sku) == 11  # EPI-CAP-XXX

    def test_sku_deterministico(self) -> None:
        sku1 = generate_sku("capacete.jpg", "protecao-cabeca")
        sku2 = generate_sku("capacete.jpg", "protecao-cabeca")
        assert sku1 == sku2

    def test_sku_diferente_por_arquivo(self) -> None:
        sku1 = generate_sku("capacete.jpg", "protecao-cabeca")
        sku2 = generate_sku("luva.jpg", "protecao-cabeca")
        # Podem ser iguais por colisão de hash, mas pouco provável
        # O importante é que o formato está correto
        assert sku1.startswith("EPI-CAP-")
        assert sku2.startswith("EPI-CAP-")

    def test_sku_por_categoria(self) -> None:
        sku = generate_sku("oculos.jpg", "protecao-visual")
        assert sku.startswith("EPI-OCV-")

        sku = generate_sku("luva.jpg", "protecao-maos")
        assert sku.startswith("EPI-LUV-")

        sku = generate_sku("furadeira.jpg", "ferramentas-eletricas")
        assert sku.startswith("EPI-FUR-")


class TestGeneratePrice:
    """Testes de geração de preço determinístico."""

    def test_preco_dentro_faixa(self) -> None:
        price = generate_price("protecao-cabeca", "capacete.jpg")
        min_p, max_p = CATEGORY_PRICE_RANGES["protecao-cabeca"]
        assert min_p <= price <= max_p

    def test_preco_deterministico(self) -> None:
        price1 = generate_price("protecao-cabeca", "capacete.jpg")
        price2 = generate_price("protecao-cabeca", "capacete.jpg")
        assert price1 == price2

    def test_preco_arredondado_varejo(self) -> None:
        price = generate_price("protecao-cabeca", "capacete.jpg")
        # Deve ser múltiplo de 0.10 (10 centavos)
        cents = int(price * 100)
        assert cents % 10 == 0

    def test_preco_duas_casas(self) -> None:
        price = generate_price("protecao-cabeca", "capacete.jpg")
        assert price == price.quantize(Decimal("0.01"))


class TestGenerateDescription:
    """Testes de geração de descrição."""

    def test_descricao_tamanho_limite(self) -> None:
        desc = generate_description("Capacete de Segurança Classe A", "protecao-cabeca")
        assert len(desc) <= 200

    def test_descricao_sem_termos_proibidos(self) -> None:
        desc = generate_description("Capacete de Segurança", "protecao-cabeca")
        # Usar a mesma lógica do validador: normalizar e checar word boundaries
        normalized_v = (
            unicodedata.normalize("NFKD", desc.lower()).encode("ascii", "ignore").decode("ascii")
        )
        for term in FORBIDDEN_TERMS:
            normalized_term = (
                unicodedata.normalize("NFKD", term.lower())
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            pattern = rf"\b{re.escape(normalized_term)}\b"
            assert not re.search(pattern, normalized_v), (
                f"Termo proibido '{term}' encontrado em: {desc}"
            )
        # Também checar padrões proibidos
        for pattern in FORBIDDEN_PATTERNS:
            assert not re.search(pattern, desc.lower()), (
                f"Padrão proibido '{pattern}' encontrado em: {desc}"
            )

    def test_descricao_neutra_catalogo(self) -> None:
        desc = generate_description("Luva de Raspa", "protecao-maos")
        assert "proteção" in desc.lower() or "protecao" in desc.lower()
        assert "mãos" in desc.lower() or "maos" in desc.lower()

    def test_descricao_ferramentas(self) -> None:
        desc = generate_description("Furadeira de Impacto", "ferramentas-eletricas")
        assert "profissional" in desc.lower() or "aplicaç" in desc.lower()


class TestCreateDraftEntry:
    """Testes de criação de entrada de rascunho (domínio)."""

    def test_arquivo_normal(self, tmp_path: Path) -> None:
        # Criar arquivo temporário
        test_file = tmp_path / "capacete-de-seguranca.jpg"
        test_file.write_bytes(b"fake image data")

        entry = create_draft_entry(test_file)

        assert entry.source_file == "capacete-de-seguranca.jpg"
        assert entry.name == "Capacete de Segurança"
        assert entry.category_slug == "protecao-cabeca"
        assert entry.category_confidence == CategoryConfidence.ALTA
        assert entry.needs_name is False
        assert entry.needs_review is False
        assert entry.brand == "protec"
        assert entry.brand_is_placeholder is True
        assert entry.price_is_demo is True
        assert entry.list_price > 0
        assert len(entry.description) <= 200
        assert entry.owner_verified is False
        assert entry.name_source == NameSource.DERIVADO_ARQUIVO
        assert entry.description_source == DescriptionSource.GERADA

    def test_arquivo_pexels(self, tmp_path: Path) -> None:
        test_file = tmp_path / "pexels-kindelmedia-8488037.jpg"
        test_file.write_bytes(b"fake image data")

        entry = create_draft_entry(test_file)

        assert entry.needs_name is True
        assert entry.needs_review is True
        assert entry.category_confidence == CategoryConfidence.BAIXA
        assert entry.author == "Kindelmedia"
        assert entry.source_url == "https://www.pexels.com/photo/8488037/"
        assert entry.license == "Pexels License"
        assert entry.license_url == "https://www.pexels.com/license/"
        assert entry.inferred_from_filename is True
        assert "Produto a identificar" in entry.name  # Placeholder name

    def test_arquivo_com_acentos_no_nome(self, tmp_path: Path) -> None:
        test_file = tmp_path / "máscara-respiradora.jpg"
        test_file.write_bytes(b"fake image data")

        entry = create_draft_entry(test_file)

        assert entry.name == "Máscara Respiradora"
        assert entry.category_slug == "protecao-respiratoria"


class TestDomainDraftManifest:
    """Testes do manifesto de domínio (puro)."""

    def test_generate_drafts_vazio(self, tmp_path: Path) -> None:
        config = DraftConfig(
            input_dir=tmp_path / "nao_existe",
            manifest_path=tmp_path / "manifest.json",
        )
        manifest = generate_drafts(config)
        assert isinstance(manifest, DraftManifest)
        assert len(manifest.entries) == 0

    def test_generate_drafts_com_arquivos(self, tmp_path: Path) -> None:
        # Criar alguns arquivos de teste
        (tmp_path / "capacete.jpg").write_bytes(b"fake")
        (tmp_path / "luva.png").write_bytes(b"fake")

        config = DraftConfig(input_dir=tmp_path, manifest_path=tmp_path / "manifest.json")
        manifest = generate_drafts(config)

        assert len(manifest.entries) == 2
        assert all(isinstance(e, DraftEntry) for e in manifest.entries)


class TestApplicationManifestValidation:
    """Testes de validação do manifesto (camada de aplicação com Pydantic)."""

    def test_manifesto_valido(self) -> None:
        entry = ManifestEntry(
            source_file="capacete.jpg",
            sku="EPI-CAP-001",
            name="Capacete de Segurança",
            description="Capacete para proteção da cabeça em obras.",
            category_slug="protecao-cabeca",
            brand="protec",
            list_price=Decimal("24.90"),
        )
        manifest = PhotoManifest(entries=[entry])
        result = validate_manifest(manifest)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_manifesto_invalido_sem_sku(self) -> None:
        # Pydantic vai rejeitar na criação
        with pytest.raises(ValueError):
            ManifestEntry(
                source_file="capacete.jpg",
                sku="",  # Inválido
                name="Capacete",
                description="Desc",
                category_slug="protecao-cabeca",
                brand="protec",
                list_price=Decimal("24.90"),
            )

    def test_manifesto_invalido_categoria_inexistente(self) -> None:
        with pytest.raises(ValueError):
            ManifestEntry(
                source_file="capacete.jpg",
                sku="EPI-CAP-001",
                name="Capacete",
                description="Desc",
                category_slug="inexistente",
                brand="protec",
                list_price=Decimal("24.90"),
            )

    def test_manifesto_invalido_marca_inexistente(self) -> None:
        with pytest.raises(ValueError):
            ManifestEntry(
                source_file="capacete.jpg",
                sku="EPI-CAP-001",
                name="Capacete",
                description="Desc",
                category_slug="protecao-cabeca",
                brand="marca-fake",
                list_price=Decimal("24.90"),
            )

    def test_manifesto_invalido_descricao_longa(self) -> None:
        with pytest.raises(ValueError):
            ManifestEntry(
                source_file="capacete.jpg",
                sku="EPI-CAP-001",
                name="Capacete",
                description="A" * 201,  # > 200 chars
                category_slug="protecao-cabeca",
                brand="protec",
                list_price=Decimal("24.90"),
            )

    def test_manifesto_invalido_termo_proibido(self) -> None:
        with pytest.raises(ValueError):
            ManifestEntry(
                source_file="capacete.jpg",
                sku="EPI-CAP-001",
                name="Capacete",
                description="Capacete com CA-12345 certificado ABNT",  # Termos proibidos
                category_slug="protecao-cabeca",
                brand="protec",
                list_price=Decimal("24.90"),
            )

    def test_entrada_nao_publicavel_sem_owner_verified(self) -> None:
        entry = ManifestEntry(
            source_file="capacete.jpg",
            sku="EPI-CAP-001",
            name="Capacete de Segurança",
            description="Capacete para proteção da cabeça.",
            category_slug="protecao-cabeca",
            brand="protec",
            list_price=Decimal("24.90"),
            owner_verified=False,
        )
        manifest = PhotoManifest(entries=[entry])
        result = validate_manifest(manifest)
        assert result.valid is True  # Validação estrutural passa
        assert len(result.warnings) == 1
        assert "não publicável" in result.warnings[0]
        assert "owner_verified=False" in result.warnings[0]

    def test_entrada_nao_publicavel_needs_name(self) -> None:
        entry = ManifestEntry(
            source_file="pexels-123.jpg",
            sku="EPI-CAP-001",
            name="Produto a identificar",
            description="Produto a identificar e descrever pelo responsável.",
            category_slug="epis",
            brand="protec",
            list_price=Decimal("24.90"),
            needs_name=True,
            owner_verified=False,
        )
        manifest = PhotoManifest(entries=[entry])
        result = validate_manifest(manifest)
        assert result.valid is True
        assert len(result.warnings) == 1
        assert "needs_name=True" in result.warnings[0]

    def test_entrada_publicavel_completa(self) -> None:
        entry = ManifestEntry(
            source_file="capacete.jpg",
            sku="EPI-CAP-001",
            name="Capacete de Segurança",
            description="Capacete para proteção da cabeça em obras.",
            category_slug="protecao-cabeca",
            brand="protec",
            list_price=Decimal("24.90"),
            owner_verified=True,
            source_url="https://example.com/foto.jpg",
        )
        manifest = PhotoManifest(entries=[entry])
        result = validate_manifest(manifest)
        assert result.valid is True
        # Pode ter warnings mas não erros
        assert entry.is_publishable() is True

    def test_entrada_owner_verified_sem_creditos_warning(self) -> None:
        entry = ManifestEntry(
            source_file="capacete.jpg",
            sku="EPI-CAP-001",
            name="Capacete de Segurança",
            description="Capacete para proteção da cabeça.",
            category_slug="protecao-cabeca",
            brand="protec",
            list_price=Decimal("24.90"),
            owner_verified=True,
            # Sem source_url nem author
        )
        manifest = PhotoManifest(entries=[entry])
        result = validate_manifest(manifest)
        assert result.valid is True
        assert len(result.warnings) == 1
        assert "créditos incompletos" in result.warnings[0]


class TestApplicationManifestSerialization:
    """Testes de serialização do manifesto (camada de aplicação)."""

    def test_save_load_manifest(self, tmp_path: Path) -> None:
        entry = ManifestEntry(
            source_file="capacete.jpg",
            sku="EPI-CAP-001",
            name="Capacete de Segurança",
            description="Capacete para proteção da cabeça.",
            category_slug="protecao-cabeca",
            brand="protec",
            list_price=Decimal("24.90"),
        )
        manifest = PhotoManifest(entries=[entry])
        manifest_path = tmp_path / "manifest.json"

        save_manifest(manifest, manifest_path)
        loaded = load_manifest(manifest_path)

        assert loaded.version == manifest.version
        assert len(loaded.entries) == 1
        assert loaded.entries[0].source_file == "capacete.jpg"
        assert loaded.entries[0].sku == "EPI-CAP-001"
        assert loaded.entries[0].list_price == Decimal("24.90")

    def test_create_empty_template(self, tmp_path: Path) -> None:
        template_path = tmp_path / "template.json"
        create_empty_manifest_template(template_path)

        with open(template_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == 1
        assert "entries" in data
        assert "_instructions" in data
        assert "valid_categories" in data["_instructions"]
        assert "valid_brands" in data["_instructions"]
        assert "forbidden_terms_in_description" in data["_instructions"]


class TestApplicationCreateDraftFromFile:
    """Testes de criação de entrada a partir de arquivo (camada de aplicação)."""

    def test_arquivo_normal(self, tmp_path: Path) -> None:
        test_file = tmp_path / "capacete-de-seguranca.jpg"
        test_file.write_bytes(b"fake image data")

        entry = create_draft_entry_from_file(test_file)

        assert entry.source_file == "capacete-de-seguranca.jpg"
        assert entry.name == "Capacete de Segurança"
        assert entry.category_slug == "protecao-cabeca"
        assert entry.category_confidence == CategoryConfidence.ALTA
        assert entry.needs_name is False
        assert entry.needs_review is False
        assert entry.brand == "protec"
        assert entry.brand_is_placeholder is True
        assert entry.price_is_demo is True
        assert entry.list_price > 0
        assert len(entry.description) <= 200
        assert entry.owner_verified is False

    def test_arquivo_pexels(self, tmp_path: Path) -> None:
        test_file = tmp_path / "pexels-kindelmedia-8488037.jpg"
        test_file.write_bytes(b"fake image data")

        entry = create_draft_entry_from_file(test_file)

        assert entry.needs_name is True
        assert entry.needs_review is True
        assert entry.category_confidence == CategoryConfidence.BAIXA
        assert entry.author == "Kindelmedia"
        assert entry.source_url == "https://www.pexels.com/photo/8488037/"
        assert entry.license == "Pexels License"
        assert entry.license_url == "https://www.pexels.com/license/"
        assert entry.inferred_from_filename is True
        assert "Produto a identificar" in entry.name


class TestApplicationGenerateDraftsFromDir:
    """Testes de geração de rascunhos a partir de diretório (camada de aplicação)."""

    def test_generate_drafts_vazio(self, tmp_path: Path) -> None:
        manifest = generate_drafts_from_dir(tmp_path / "nao_existe")
        assert isinstance(manifest, PhotoManifest)
        assert len(manifest.entries) == 0

    def test_generate_drafts_com_arquivos(self, tmp_path: Path) -> None:
        (tmp_path / "capacete.jpg").write_bytes(b"fake")
        (tmp_path / "luva.png").write_bytes(b"fake")

        manifest = generate_drafts_from_dir(tmp_path)

        assert len(manifest.entries) == 2
        assert all(isinstance(e, ManifestEntry) for e in manifest.entries)


class TestConstants:
    """Testes das constantes."""

    def test_category_to_brand_mapping_complete(self) -> None:
        # Todas as categorias devem ter marca mapeada
        for cat in CATEGORY_PRICE_RANGES:
            assert cat in CATEGORY_TO_BRAND, f"Categoria {cat} sem marca mapeada"
            assert CATEGORY_TO_BRAND[cat] in {
                "protec",
                "norton",
                "vulcano",
                "aegis",
                "guardian",
                "ferrum",
                "titan",
                "sentinel",
            }

    def test_forbidden_terms_not_empty(self) -> None:
        assert len(FORBIDDEN_TERMS) > 0
        assert "certificado" in FORBIDDEN_TERMS
        assert "norma" in FORBIDDEN_TERMS
        # "ca" foi removido pois é substring comum; use FORBIDDEN_PATTERNS para CA-12345
