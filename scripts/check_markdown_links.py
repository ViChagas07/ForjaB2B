#!/usr/bin/env python3
"""Verifica links internos relativos em arquivos Markdown do repositorio.

Uso:
    python scripts/check_markdown_links.py [--root .] [--quiet]

Regras:
- Links http(s), mailto e tel sao ignorados (nao ha checagem de rede).
- Ancora pura (#secao) e ignorada.
- Alvos relativos sao resolvidos a partir do diretorio do arquivo.
- Codigo em blocos cercados por ``` e inline `...` e removido antes da analise.
- Arquivos historicos congelados (docs/history/) e o log docs/agent/PROGRESS.md
  sao ignorados por padrao; eles preservam caminhos da epoca em que foram escritos.
  Use --include-history para inclui-los.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

_DEFAULT_SKIP = {
    Path("docs/agent/PROGRESS.md"),
}


def _strip_code(text: str) -> str:
    return _INLINE_CODE_RE.sub("", _FENCE_RE.sub("", text))


def _iter_markdown(root: Path, include_history: bool) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(
            part in {".git", "node_modules", ".venv", ".mypy_cache"}
            for part in rel.parts
        ):
            continue
        if not include_history and (
            rel.parts[:2] == ("docs", "history") or rel in _DEFAULT_SKIP
        ):
            continue
        files.append(path)
    return files


def _target_path(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(" ", 1)[0]
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target or target.startswith("#"):
        return None
    if _SCHEME_RE.match(target) or target.startswith("//"):
        return None
    return unquote(target)


def check(root: Path, *, include_history: bool = False) -> list[tuple[Path, int, str]]:
    broken: list[tuple[Path, int, str]] = []
    for path in _iter_markdown(root, include_history):
        raw = path.read_bytes()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("utf-16")
        text = _strip_code(content)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in _LINK_RE.finditer(line):
                target = _target_path(match.group(1))
                if target is None:
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    broken.append((path.relative_to(root), line_number, target))
    return broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica links internos de Markdown.")
    parser.add_argument("--root", default=".", help="Raiz do repositorio (padrao: .).")
    parser.add_argument(
        "--include-history", action="store_true", help="Inclui docs/history e PROGRESS."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="So imprime se houver erro."
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    broken = check(root, include_history=args.include_history)
    if broken:
        for path, line, target in broken:
            print(f"{path}:{line}: link quebrado: {target}")
        print(f"\n{len(broken)} link(s) quebrado(s).")
        return 1
    if not args.quiet:
        total = len(_iter_markdown(root, args.include_history))
        print(f"OK: {total} arquivo(s) Markdown, nenhum link interno quebrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
