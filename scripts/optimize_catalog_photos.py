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
import re
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

# (diretorio de origem, arquivo original, SKU, modo) — mapeamento documentado em
# docs/illustrations/PHOTO_MAPPING.md (confianca alta). Modos: "crop" = recorte
# quadrado central; "fit" = composicao em fundo neutro (quando o recorte central
# cortaria o objeto de forma evidente).
PHOTO_SOURCES: list[tuple[Path, str, str, str]] = [
    # Lote 1 (brand/): fotos originais do responsavel.
    (SOURCE_DIR, "botina-1242304473-30156647.jpg", "BOT-001", "fit"),
    (SOURCE_DIR, "capacete-para-obra-38070.jpg", "EPI-CAP-001", "crop"),
    (SOURCE_DIR, "furadeira-3877525.jpg", "MAQ-PAR-004", "crop"),
    (SOURCE_DIR, "kit-antiqueda-34019840.jpg", "QUE-001", "crop"),
    (SOURCE_DIR, "luva-de-obra-8488007.jpg", "LUV-003", "fit"),
    (SOURCE_DIR, "mascara-de-gas-3435524-5499417.jpg", "RES-006", "fit"),
    (SOURCE_DIR, "máscara-respiradora-8487784.jpg", "RES-005", "fit"),
    (SOURCE_DIR, "protetor-auricular-6791514.jpg", "AUD-002", "crop"),
    (SOURCE_DIR, "óculos-de-obra51320673-8352127.jpg", "OCV-003", "crop"),
    # Lote 2 (catalog/photos/): fotos nomeadas pelo proprio produto.
    (OUTPUT_DIR, "Abafador de Ruído Acoplado ao Capacete.jpg", "AUD-003", "crop"),
    (OUTPUT_DIR, "Bomba d'Água Autoaspirante.jpg", "MAQ-009", "crop"),
    (OUTPUT_DIR, "Bota de Segurança Bico Composite.jpg", "BOT-002", "crop"),
    (OUTPUT_DIR, "Botas de Segurança Impermeáveis.jpg", "BOT-003", "crop"),
    (OUTPUT_DIR, "Botina Eletricista.jpg", "BOT-004", "crop"),
    (OUTPUT_DIR, "Capacete de Segurança Classe A Aba Frontal.webp", "CAP-002", "crop"),
    (OUTPUT_DIR, "Capacete de Segurança Classe B com Jugular.webp", "CAP-003", "crop"),
    (OUTPUT_DIR, "Capacete de Segurança Conjugado.webp", "CAP-004", "crop"),
    (OUTPUT_DIR, "Capacete de Segurança Descontinuado.png", "CAP-005", "crop"),
    (OUTPUT_DIR, "Cinturão de Segurança Abdominal.webp", "QUE-003", "fit"),
    (OUTPUT_DIR, "Compressor de Ar 100L.jpg", "MAQ-005", "crop"),
    (OUTPUT_DIR, "Esmerilhadeira Angular 115mm.jpg", "FUR-003", "crop"),
    (OUTPUT_DIR, "Furadeira de Impacto 850W.jpg", "FUR-001", "fit"),
    (OUTPUT_DIR, "Furadeiras de Bancada 500W.jpg", "FUR-002", "crop"),
    (OUTPUT_DIR, "Luva Anticorte Nível 5.jpg", "LUV-007", "crop"),
    (OUTPUT_DIR, "Luva de Látex Forrada.jpg", "LUV-008", "crop"),
    (OUTPUT_DIR, "Luva de Raspa Premium.jpg", "EPI-LUV-002", "crop"),
    (OUTPUT_DIR, "Luva de Vaqueta Petroleira.jpg", "LUV-006", "crop"),
    (OUTPUT_DIR, "Luva Nitrílica Descartável.jpg", "LUV-005", "fit"),
    (OUTPUT_DIR, "Máscara de Proteção PFF1.jpg", "RES-007", "crop"),
    (OUTPUT_DIR, "Oculos de Proteção Fumê.jpg", "OCV-002", "crop"),
    (OUTPUT_DIR, "Politriz de Bancada.jpg", "MAQ-007", "crop"),
    (OUTPUT_DIR, "Prensa Hidráulica 15T.jpg", "MAQ-006", "crop"),
    (OUTPUT_DIR, "Protetor Auricular Plug Silicone.jpg", "AUD-001", "crop"),
    (OUTPUT_DIR, "Respirador Panorâmico.jpg", "RES-008", "fit"),
    (OUTPUT_DIR, "Respirador PFF2.jpg", "EPI-RES-003", "fit"),
    (OUTPUT_DIR, "Retífica Reta 500W.jpg", "FUR-005", "crop"),
    (OUTPUT_DIR, "Sapato de Segurança Sport.jpg", "BOT-005", "crop"),
    (OUTPUT_DIR, "Serra Circular 7 14.jpg", "FUR-004", "fit"),
    (OUTPUT_DIR, "Serra de Bancada 10.jpg", "MAQ-008", "crop"),
    (OUTPUT_DIR, "Talabarte Duplo I e Y.jpg", "QUE-002", "crop"),
    (OUTPUT_DIR, "Torno de Bancada.jpg", "MAQ-010", "crop"),
    (OUTPUT_DIR, "Trava Queda Deslizante.jpg", "QUE-004", "crop"),
    (OUTPUT_DIR, "Óculos de Proteção Incolor.jpg", "OCV-001", "fit"),
    (OUTPUT_DIR, "Óculos de Proteção para Sobrepor.jpg", "OCV-005", "crop"),
    (OUTPUT_DIR, "Óculos de Segurança Antiembaçante.jpg", "OCV-004", "crop"),
]


def _is_sku_output(name: str) -> bool:
    """Saida nomeada por SKU: 'bot-001.webp' (minusculas, sem espacos)."""
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*\.webp", name))


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


def _optimize_one(source_dir: Path, filename: str, sku: str, mode: str) -> bool:
    source = source_dir / filename
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
        # Apenas saidas nomeadas por SKU (originais do responsavel nao contam).
        outputs = sorted(OUTPUT_DIR.glob("*.webp"))
        outputs = [target for target in outputs if _is_sku_output(target.name)]
        if not outputs:
            print("AVISO: nenhuma saida encontrada")
            return 1
        for target in outputs:
            if not _verify_target(target):
                failures += 1
        return failures
    for source_dir, filename, sku, mode in PHOTO_SOURCES:
        if not _optimize_one(source_dir, filename, sku, mode):
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
