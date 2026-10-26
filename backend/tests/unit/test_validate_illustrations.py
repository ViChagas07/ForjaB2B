"""Testes do validador de ilustracoes (Prompt 10, B3)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = REPO_ROOT / "scripts" / "validate_illustrations.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_illustrations", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TILE = '<rect width="512" height="512" rx="96" fill="#0F172A"/>'


def _svg(body: str, *, viewbox: str = "0 0 512 512", role: str = "img") -> bytes:
    title = "<title>Luva de raspa</title>"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="{role}">'
        f"{title}{TILE}{body}</svg>"
    ).encode()


def test_svg_valido_passa() -> None:
    module = _load()
    body = (
        '<g fill="none" stroke="#F8FAFC" stroke-width="14" stroke-linecap="round">'
        '<path d="M150 344 H326"/></g>'
        '<path d="M150 344 H326" fill="none" stroke="#F97316" stroke-width="14"/>'
    )
    assert module.validate_svg(_svg(body), name="t.svg") == []


def test_viewbox_errado_e_ausencia_de_role_falham() -> None:
    module = _load()
    body = '<path d="M1 1" stroke="#F97316" stroke-width="14" fill="none"/>'
    errors = module.validate_svg(_svg(body, viewbox="0 0 64 64"), name="t.svg")
    assert any("viewBox" in e for e in errors)
    errors = module.validate_svg(_svg(body, role="presentation"), name="t.svg")
    assert any("role" in e for e in errors)


def test_elementos_proibidos_e_referencias_externas_falham() -> None:
    module = _load()
    body = '<script href="https://evil.example/x.js"/>'
    errors = module.validate_svg(_svg(body), name="t.svg")
    assert any("proibido" in e for e in errors)
    body = '<path href="#x" stroke="#F97316" fill="none" stroke-width="14"/>'
    errors = module.validate_svg(_svg(body), name="t.svg")
    assert any("referencia externa" in e for e in errors)


def test_cores_fora_da_paleta_falham() -> None:
    module = _load()
    body = '<circle cx="10" cy="10" r="5" fill="#FF0000"/>'
    errors = module.validate_svg(_svg(body), name="t.svg")
    assert any("paleta" in e for e in errors)


def test_acento_duplicado_falha() -> None:
    module = _load()
    body = (
        '<path d="M1 1" stroke="#F97316" stroke-width="14" fill="none"/>'
        '<path d="M2 2" stroke="#F97316" stroke-width="14" fill="none"/>'
    )
    errors = module.validate_svg(_svg(body), name="t.svg")
    assert any("acento" in e for e in errors)


def test_titulo_ausente_falha() -> None:
    module = _load()
    source = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img">'
        f'{TILE}<path d="M1 1" stroke="#F97316" stroke-width="14" fill="none"/></svg>'
    ).encode()
    errors = module.validate_svg(source, name="t.svg")
    assert any("title" in e for e in errors)


def test_tamanho_acima_de_3kb_falha() -> None:
    module = _load()
    body = (
        '<path d="M1 1 '
        + " ".join(["L1 1"] * 800)
        + '" stroke="#F97316" fill="none" stroke-width="14"/>'
    )
    errors = module.validate_svg(_svg(body), name="t.svg")
    assert any("limite" in e for e in errors)


def test_xml_mal_formado_falha() -> None:
    module = _load()
    errors = module.validate_svg(b"<svg><path></svg>", name="t.svg")
    assert any("mal formado" in e for e in errors)


def test_stroke_width_diferente_falha() -> None:
    module = _load()
    body = '<path d="M1 1" stroke="#F8FAFC" stroke-width="3" fill="none"/>'
    errors = module.validate_svg(_svg(body), name="t.svg")
    assert any("stroke-width" in e for e in errors)


def test_cruzamento_familias() -> None:
    module = _load()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "FAMILIES.md").write_text(
            "| Chave | SKUs | Descricao |\n|---|---|---|\n| luva-de-raspa | LUV-004 | Luva. |\n",
            encoding="utf-8",
        )
        (root / "ilhas").mkdir()
        # Familia sem arquivo:
        assert module.validate_families(root / "FAMILIES.md", root / "ilhas") == [
            "FAMILIES.md: familia 'luva-de-raspa' sem arquivo luva-de-raspa.svg"
        ]
        # Arquivo sem familia:
        (root / "ilhas" / "luva-de-raspa.svg").write_text("x", encoding="utf-8")
        (root / "ilhas" / "fantasma.svg").write_text("x", encoding="utf-8")
        errors = module.validate_families(root / "FAMILIES.md", root / "ilhas")
        assert errors == ["fantasma.svg: arquivo sem entrada em FAMILIES.md"]


def test_arquivos_reais_passam() -> None:
    module = _load()
    illustrations = REPO_ROOT / "frontend" / "public" / "catalog" / "illustrations"
    failures: list[str] = []
    for path in sorted(illustrations.glob("*.svg")):
        failures.extend(module.validate_svg(path.read_bytes(), name=path.name))
    families_md = REPO_ROOT / "docs" / "illustrations" / "FAMILIES.md"
    failures.extend(module.validate_families(families_md, illustrations))
    for extra in ("protecao-respiratoria.svg", "protecao-maos.svg"):
        path = REPO_ROOT / "backend" / "app" / "static" / "catalog" / extra
        failures.extend(module.validate_svg(path.read_bytes(), name=extra))
    assert failures == []
