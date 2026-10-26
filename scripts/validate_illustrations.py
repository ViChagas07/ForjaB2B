"""Validador das ilustracoes SVG do catalogo (Prompt 10, Parte B3).

Falha (exit 1) se qualquer arquivo em ``frontend/public/catalog/illustrations/``:
  * nao for XML bem formado;
  * tiver viewBox diferente de ``0 0 512 512``;
  * exceder 3 KB;
  * usar elementos proibidos (script, foreignObject, image, style, use) ou
    referencias externas (href/xlink:href);
  * usar cores fora da paleta permitida (ladrilho #0F172A, branco #F8FAFC,
    acento #F97316) ou largura de traco diferente de 14;
  * nao ter ``role="img"`` ou ``<title>`` com o nome da familia;
  * nao tiver exatamente UM elemento de acento laranja;
  * estiver citado em FAMILIES.md sem arquivo, ou sem entrada no FAMILIES.md.

Tambem valida, com as mesmas regras, as ilustracoes de categoria refeitas em
``backend/app/static/catalog`` (protecao-respiratoria.svg, protecao-maos.svg).

Uso: ``python scripts/validate_illustrations.py`` (caminhos relativos a raiz).
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ILLUSTRATIONS_DIR = REPO_ROOT / "frontend" / "public" / "catalog" / "illustrations"
FAMILIES_MD = REPO_ROOT / "docs" / "illustrations" / "FAMILIES.md"
CATEGORY_DIR = REPO_ROOT / "backend" / "app" / "static" / "catalog"
CATEGORY_EXTRA = ["protecao-respiratoria.svg", "protecao-maos.svg"]
# Arquivos de infraestrutura no mesmo diretorio, fora do mapa de familias:
# fallback final de erro do componente ProductImage (frontend, sem API).
NON_FAMILY_FILES = {"generic.svg"}

MAX_BYTES = 3072
VIEWBOX = "0 0 512 512"
ALLOWED_COLORS = {"#0f172a", "#f8fafc", "#f97316"}
ACCENT = "#f97316"
STROKE_WIDTH = "14"
FORBIDDEN_TAGS = {"script", "foreignobject", "image", "style", "use"}
COLOR_ATTRS = ("fill", "stroke")

_SVG = "{http://www.w3.org/2000/svg}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _check_attrs(element, tag: str, errors: list[str], accent: dict[str, int]) -> None:
    attrs = element.attrib
    if any(key.rsplit("}", 1)[-1] in {"href", "hreflang"} for key in attrs):
        errors.append(f"referencia externa proibida em <{tag}>")
    if "style" in attrs:
        errors.append(f"atributo style proibido em <{tag}>")
    colors = {attrs[a].strip().lower() for a in COLOR_ATTRS if a in attrs}
    invalid = colors - ALLOWED_COLORS - {"none"}
    if invalid:
        errors.append(f"cores fora da paleta em <{tag}>: {sorted(invalid)}")
    if ACCENT in colors:
        accent["count"] += 1
    width = attrs.get("stroke-width")
    if width is not None and width != STROKE_WIDTH:
        errors.append(f'stroke-width "{width}" != {STROKE_WIDTH} em <{tag}>')


def _check_header(root, errors: list[str], fail) -> None:
    if root.get("viewBox") != VIEWBOX:
        fail(f'viewBox deve ser "{VIEWBOX}" (obtido "{root.get("viewBox")}")')
    if root.get("role") != "img":
        fail('role="img" obrigatoria no elemento raiz')
    title = root.find(f"{_SVG}title")
    if title is None or not (title.text or "").strip():
        fail("<title> obrigatorio com o nome da familia em portugues")


def validate_svg(source: bytes, *, name: str = "svg") -> list[str]:
    """Retorna a lista de violacoes (vazia = valido). Funcao pura."""
    errors: list[str] = []

    def fail(message: str) -> None:
        errors.append(f"{name}: {message}")

    if len(source) > MAX_BYTES:
        fail(f"tamanho {len(source)} B acima do limite de {MAX_BYTES} B")
    try:
        # Entrada confiavel: arquivos gerados por este mesmo pipeline no repo
        # (sem conteudo de terceiros); defusedxml seria dependencia extra.
        root = ET.fromstring(source.decode("utf-8"))  # noqa: S314
    except (ET.ParseError, UnicodeDecodeError) as exc:
        fail(f"XML mal formado: {exc}")
        return errors

    if _local(root.tag) != "svg":
        fail("raiz nao e <svg>")
        return errors
    _check_header(root, errors, fail)

    accent: dict[str, int] = {"count": 0}
    for element in root.iter():
        tag = _local(element.tag)
        if tag in FORBIDDEN_TAGS:
            fail(f"elemento proibido <{tag}>")
            continue
        _check_attrs(element, tag, errors, accent)
    if accent["count"] != 1:
        fail(f"exatamente 1 elemento de acento {ACCENT} obrigatorio (obtido {accent['count']})")

    return errors


def _family_keys(families_md: Path) -> tuple[dict[str, str], list[str]]:
    """Extrai (chave -> linha) da tabela de FAMILIES.md (chaves sao slugs)."""
    keys: dict[str, str] = {}
    for line in families_md.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", cells[0]):
            continue
        keys[cells[0]] = line
    return keys, []


def validate_families(families_md: Path, illustrations_dir: Path) -> list[str]:
    """Cruza FAMILIES.md com os arquivos existentes."""
    errors: list[str] = []
    if not families_md.exists():
        return [f"{families_md}: arquivo ausente"]
    keys, _ = _family_keys(families_md)
    files = {path.name for path in illustrations_dir.glob("*.svg")}
    for key in keys:
        if f"{key}.svg" not in files:
            errors.append(f"FAMILIES.md: familia '{key}' sem arquivo {key}.svg")
    for file in sorted(files - NON_FAMILY_FILES):
        if file.removesuffix(".svg") not in keys:
            errors.append(f"{file}: arquivo sem entrada em FAMILIES.md")
    return errors


def main() -> int:
    failures = 0
    paths = sorted(ILLUSTRATIONS_DIR.glob("*.svg"))
    paths += [CATEGORY_DIR / extra for extra in CATEGORY_EXTRA if (CATEGORY_DIR / extra).exists()]
    for path in paths:
        errors = validate_svg(path.read_bytes(), name=path.name)
        for error in errors:
            print(f"FALHA: {error}")
        failures += len(errors)
        if not errors:
            print(f"OK: {path.name} ({path.stat().st_size} B)")
    if FAMILIES_MD.exists():
        for error in validate_families(FAMILIES_MD, ILLUSTRATIONS_DIR):
            print(f"FALHA: {error}")
            failures += 1
    else:
        print(f"AVISO: {FAMILIES_MD} ausente (cruzamento de familias ignorado)")
    print(f"Total de violacoes: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
