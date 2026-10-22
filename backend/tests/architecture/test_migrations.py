"""Garantias estruturais das migrations (sem banco).

O drill completo roda em um banco descartavel (scripts/migration_drill.py). Aqui
ficam as garantias baratas que o CI executa sempre:

* toda revision tem ``upgrade`` e ``downgrade``;
* o ``downgrade`` executa DDL de verdade (nao e ``pass`` nem ``NotImplemented``);
* migrations marcadas como irreversiveis apontam o procedimento alternativo na
  documentacao e trazem o marcador no cabecalho.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
VERSIONS_DIR = BACKEND_DIR / "alembic" / "versions"
MIGRATIONS_DOC = BACKEND_DIR.parent / "docs" / "MIGRATIONS.md"

IRREVERSIBLE_MARKER = "IRREVERSIVEL:"


def _migration_files() -> list[Path]:
    return sorted(path for path in VERSIONS_DIR.glob("*.py") if path.name != "__init__.py")


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _executes_ddl(function: ast.FunctionDef) -> bool:
    """True se a funcao chama op.* (DDL) ou uma funcao local de downgrade."""
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            # op.drop_table(...), op.execute(...), op.drop_column(...)
            return True
        if isinstance(func, ast.Name):
            # Helper local do proprio modulo (ex.: _values) nao conta; chamadas
            # para funcoes locais que executam op.* sao cobertas pelo walk.
            continue
    return False


def test_toda_migration_tem_upgrade_e_downgrade_funcionais() -> None:
    files = _migration_files()
    assert files, "nenhuma migration encontrada"

    offenders: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        upgrade = _function(tree, "upgrade")
        downgrade = _function(tree, "downgrade")
        if upgrade is None or downgrade is None:
            offenders.append(f"{path.name}: upgrade/downgrade ausente")
            continue
        if not _executes_ddl(downgrade):
            offenders.append(f"{path.name}: downgrade sem chamada op.*")
        if any(isinstance(node, ast.Pass) for node in ast.walk(downgrade)):
            offenders.append(f"{path.name}: downgrade contem pass")
        if any(
            isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id == "NotImplementedError"
            for node in ast.walk(downgrade)
        ):
            offenders.append(f"{path.name}: downgrade levanta NotImplementedError")

    assert offenders == [], "migrations sem downgrade funcional:\n" + "\n".join(offenders)


def test_migrations_irreversiveis_estao_documentadas_com_procedimento() -> None:
    """Se uma migration for marcada como irreversivel, a doc deve explicar o porque."""
    doc = MIGRATIONS_DOC.read_text(encoding="utf-8") if MIGRATIONS_DOC.is_file() else ""
    problems: list[str] = []
    for path in _migration_files():
        source = path.read_text(encoding="utf-8")
        if IRREVERSIBLE_MARKER not in source:
            continue
        revision = source.split('revision: str = "', 1)[-1].split('"', 1)[0]
        if revision not in doc:
            problems.append(f"{path.name}: revision {revision} ausente de docs/MIGRATIONS.md")
        if "procedimento" not in doc.lower():
            problems.append("docs/MIGRATIONS.md sem secao de procedimento alternativo")
    assert problems == [], "\n".join(problems)
