"""Consistencia do mapeamento imagem -> produto (Prompt 10, A3/B5)."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.db.seeds import _ALL_PRODUCTS, _PRODUCT_IMAGES

REPO_ROOT = Path(__file__).resolve().parents[3]
PHOTOS_DIR = REPO_ROOT / "frontend" / "public" / "catalog" / "photos"
ILLUSTRATIONS_DIR = REPO_ROOT / "frontend" / "public" / "catalog" / "illustrations"

# SKUs com foto (Prompt 10 lote 1 + lote 2 nomeado pelo responsavel + lote 3).
PHOTO_SKUS = {
    "EPI-CAP-001",
    "MAQ-PAR-004",
    "QUE-001",
    "LUV-003",
    "RES-005",
    "RES-006",
    "AUD-002",
    "OCV-003",
    "BOT-001",
    "AUD-003",
    "MAQ-009",
    "BOT-002",
    "BOT-003",
    "BOT-004",
    "CAP-002",
    "CAP-003",
    "CAP-004",
    "CAP-005",
    "QUE-003",
    "MAQ-005",
    "FUR-003",
    "FUR-001",
    "FUR-002",
    "LUV-007",
    "LUV-008",
    "EPI-LUV-002",
    "LUV-006",
    "LUV-005",
    "RES-007",
    "OCV-002",
    "MAQ-007",
    "MAQ-006",
    "AUD-001",
    "RES-008",
    "EPI-RES-003",
    "FUR-005",
    "BOT-005",
    "FUR-004",
    "MAQ-008",
    "QUE-002",
    "MAQ-010",
    "QUE-004",
    "OCV-001",
    "OCV-005",
    "OCV-004",
    "LUV-004",
    "RES-004",
    "AUD-004",
}


def _skus() -> dict[str, object]:
    return {cast_str(product["sku"]): product for product in _ALL_PRODUCTS}


def cast_str(value: object) -> str:
    assert isinstance(value, str)
    return value


def test_todo_sku_mapeado_existe_no_seed() -> None:
    catalog = _skus()
    for sku in _PRODUCT_IMAGES:
        assert sku in catalog, f"{sku} mapeado mas inexistente no seed"


def test_fotos_mapeiam_apenas_skus_aprovados_e_arquivo_existe() -> None:
    catalog = _skus()
    photos = {sku: url for sku, url in _PRODUCT_IMAGES.items() if url.endswith(".webp")}
    assert set(photos) == PHOTO_SKUS
    for sku, url in photos.items():
        # Um produto por foto: o nome do arquivo deriva do SKU.
        assert url == f"/catalog/photos/{sku.lower()}.webp"
        assert (PHOTOS_DIR / url.rsplit("/", 1)[-1]).exists(), f"arquivo ausente: {url}"
        assert catalog[sku] is not None


def test_ilustracoes_existem_e_sao_da_familia_correta() -> None:
    for url in _PRODUCT_IMAGES.values():
        if not url.endswith(".svg"):
            continue
        assert url.startswith("/catalog/illustrations/")
        assert (ILLUSTRATIONS_DIR / url.rsplit("/", 1)[-1]).exists(), f"arquivo ausente: {url}"


def test_cobertura_todos_os_vendaveis_com_imagem_especifica() -> None:
    # TODOS os produtos ACTIVE (vendaveis) tem foto ou ilustracao especifica.
    catalog = _skus()
    sellable = [sku for sku, product in catalog.items() if cast_str(product["status"]) == "ACTIVE"]
    sem_imagem = [sku for sku in sellable if sku not in _PRODUCT_IMAGES]
    assert sem_imagem == []
    # Fora de linha mapeados (CAP-005 e MAQ-010 com foto; OCV-006/LUV-009 com
    # ilustracao) nao afetam a vitrine.
    inactive_mapeados = [
        sku for sku in _PRODUCT_IMAGES if cast_str(catalog[sku]["status"]) != "ACTIVE"
    ]
    assert set(inactive_mapeados) <= {"CAP-005", "OCV-006", "LUV-009", "MAQ-010"}
