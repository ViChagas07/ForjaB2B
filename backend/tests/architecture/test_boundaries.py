"""Testes de arquitetura: contratos import-linter e ausencia de dominio na Fase 0.

Os contratos em .import-linter sao executados de verdade (grimp constroi o
grafo de imports do pacote app). Qualquer violacao de camadas, independencia
de modulos ou pureza de dominio falha este teste e o CI.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
IMPORT_LINTER_CONFIG = BACKEND_DIR / ".import-linter"
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"


def test_import_linter_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlinter.cli import lint_imports

    monkeypatch.chdir(BACKEND_DIR)
    exit_code = lint_imports(config_filename=str(IMPORT_LINTER_CONFIG), no_cache=True, no_logo=True)
    assert exit_code == 0, "Violacao de contrato arquitetural (ver saida do import-linter)"


def _assigned_literal(tree: ast.Module, name: str) -> object | None:
    """Devolve o valor literal da atribuicao de nivel de modulo ``name``, se houver."""
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return cast(object, ast.literal_eval(node.value))
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return cast(object, ast.literal_eval(node.value))
    return None


def _revision_meta(path: Path) -> tuple[str, str | None]:
    """Extrai (revision, down_revision) de um arquivo de migration via AST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    revision = _assigned_literal(tree, "revision")
    down_revision = _assigned_literal(tree, "down_revision")
    assert isinstance(revision, str), f"Migration {path.name} sem variavel 'revision'"
    return revision, down_revision if isinstance(down_revision, str) else None


def test_alembic_revisions_de_dominio_formam_cadeia() -> None:
    """Fase 1 introduz migrations de dominio com ids unicos e cadeia valida."""
    revisions = list(VERSIONS_DIR.glob("*.py"))
    assert revisions != [], "Fase 1 deve ter migrations de dominio em alembic/versions"

    ids: dict[str, str | None] = {}
    for path in sorted(revisions):
        revision, down_revision = _revision_meta(path)
        assert revision not in ids, f"revision duplicada: {revision}"
        ids[revision] = down_revision

    known: set[str] = set(ids)
    for revision, down_revision in ids.items():
        if down_revision is None:
            continue
        assert down_revision in known, (
            f"revision {revision} aponta para down_revision inexistente {down_revision}"
        )
    roots = [r for r, d in ids.items() if d is None]
    assert len(roots) == 1, f"Esperada uma unica raiz de migrations, encontradas: {roots}"


def test_backend_nao_usa_em_dash() -> None:
    """Regra de estilo do projeto: zero travessao longo (em dash) no backend."""
    offenders: list[str] = []
    for path in BACKEND_DIR.rglob("*.py"):
        ignored = {".venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
        if any(part in ignored for part in path.parts):
            continue
        if "\u2014" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(BACKEND_DIR)))
    assert offenders == [], f"Em dash encontrado em: {offenders}"


def test_nenhum_type_ignore_no_codigo() -> None:
    """Zero supressoes de tipagem para silenciar erros do mypy."""
    needle = "type" + ": ignore"  # montagem dinamica evita auto-referencia
    offenders: list[str] = []
    for path in BACKEND_DIR.rglob("*.py"):
        ignored = {".venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
        if any(part in ignored for part in path.parts):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if needle in line:
                offenders.append(f"{path.relative_to(BACKEND_DIR)}:{lineno}")
    assert offenders == [], f"supressao de tipagem encontrada em: {offenders}"
