"""Otimiza e publica as fotos de produto do catalogo (Prompt 10, Parte A2).

Entrada : fotos originais (JPEG) em ``frontend/public/brand/`` fornecidas pelo
          responsavel (origem declarada: Pexels).
Saida   : ``frontend/public/catalog/photos/<sku-em-minusculas>.webp`` —
          640x640, WebP, ate 80 KB, sem metadados (EXIF/GPS removidos).

Modos por foto (documentados em docs/illustrations/PHOTO_MAPPING.md):
  * ``crop``: recorte quadrado central (padrao).
  * ``fit`` : quando o recorte central cortaria o objeto de forma evidente
              (composicao em fundo neutro #F4F2ED, que combina com o ladrilho
              claro do app).

O script e IDEMPOTENTE: mesma entrada produz a mesma saida (sem timestamps) e
reexecutar reescreve os mesmos bytes. Ferramenta de desenvolvimento: nao roda
em runtime. Depende apenas de Pillow.

Uso:
    python scripts/optimize_catalog_photos.py            # otimiza
    python scripts/optimize_catalog_photos.py --verify   # confere EXIF/tamanho
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "frontend" / "public" / "brand"
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "catalog" / "photos"

SIZE = 640
MAX_BYTES = 80_000
NEUTRAL_BG = (244, 242, 237)  # #F4F2ED (secundaria clara do tema)
FIT_MARGIN = 40  # px de respiro do objeto dentro do quadro
QUALITY_START, QUALITY_FLOOR, QUALITY_STEP = 82, 40, 2

# (arquivo original, SKU, modo) — decidido em PHOTO_MAPPING.md (confianca alta).
PHOTO_SOURCES: list[tuple[str, str, str]] = [
    ("botina-1242304473-30156647.jpg", "BOT-001", "fit"),
    ("capacete-para-obra-38070.jpg", "EPI-CAP-001", "crop"),
    ("furadeira-3877525.jpg", "MAQ-PAR-004", "crop"),
    ("kit-antiqueda-34019840.jpg", "QUE-001", "crop"),
    ("luva-de-obra-8488007.jpg", "LUV-003", "fit"),
    ("mascara-de-gas-3435524-5499417.jpg", "RES-006", "fit"),
    ("máscara-respiradora-8487784.jpg", "RES-005", "fit"),
    ("protetor-auricular-6791514.jpg", "AUD-002", "crop"),
    ("óculos-de-obra51320673-8352127.jpg", "OCV-003", "crop"),
]


def _center_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _fit_on_neutral(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (SIZE, SIZE), NEUTRAL_BG)
    inner = SIZE - 2 * FIT_MARGIN
    scaled = ImageOps.contain(image, (inner, inner))
    offset = ((SIZE - scaled.width) // 2, (SIZE - scaled.height) // 2)
    canvas.paste(scaled, offset)
    return canvas


def _compose(image: Image.Image, mode: str) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    if mode == "crop":
        return _center_square(image).resize((SIZE, SIZE), Image.LANCZOS)
    if mode == "fit":
        return _fit_on_neutral(image)
    raise ValueError(f"modo desconhecido: {mode}")


def _encode(image: Image.Image) -> tuple[bytes, int]:
    import io

    for quality in range(QUALITY_START, QUALITY_FLOOR - 1, -QUALITY_STEP):
        memory = io.BytesIO()
        image.save(memory, format="WEBP", quality=quality, method=6, exact=False)
        payload = memory.getvalue()
        if len(payload) <= MAX_BYTES or quality == QUALITY_FLOOR:
            return payload, quality
    raise AssertionError("inalcancavel")


def _verify_target(target: Path) -> bool:
    """Verifica um WebP existente; True se OK."""
    with Image.open(target) as image:
        problems = []
        if image.size != (SIZE, SIZE):
            problems.append(f"dimensoes {image.size}")
        if image.getexif() != {}:
            problems.append("EXIF presente")
    if target.stat().st_size > MAX_BYTES:
        problems.append(f"{target.stat().st_size:,} B > 80 KB")
    if problems:
        print(f"FALHA: {target.name}: {'; '.join(problems)}")
        return False
    print(f"VERIFICADO: {target.name} ({target.stat().st_size:,} B, sem EXIF)")
    return True


def _optimize_one(filename: str, sku: str, mode: str) -> bool:
    source = SOURCE_DIR / filename
    target = OUTPUT_DIR / f"{sku.lower()}.webp"
    if not source.exists():
        print(f"FALHA: origem ausente {source}")
        return False
    payload, quality = _encode(_compose(Image.open(source), mode))
    target.write_bytes(payload)
    has_exif = Image.open(target).getexif() != {}
    ok = len(payload) <= MAX_BYTES and not has_exif
    status = "OK" if ok else "FALHA"
    print(
        f"{status}: {filename} -> {target.name} ({len(payload):,} B, q={quality}, exif={has_exif})"
    )
    return ok


def optimize(verify_only: bool) -> int:
    failures = 0
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if verify_only:
        for target in sorted(OUTPUT_DIR.glob("*.webp")):
            if not _verify_target(target):
                failures += 1
        return failures
    for filename, sku, mode in PHOTO_SOURCES:
        if not _optimize_one(filename, sku, mode):
            failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="apenas verifica a saida existente")
    args = parser.parse_args()
    failures = optimize(verify_only=args.verify)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
