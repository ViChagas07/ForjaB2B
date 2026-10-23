"""Exporta o contrato OpenAPI de forma deterministica.

Uso (a partir de backend/):

    python scripts/export_openapi.py                # grava docs/api/openapi.json
    python scripts/export_openapi.py --check        # falha se o snapshot divergir
    python scripts/export_openapi.py --output X.json

O JSON usa chaves ordenadas, indentacao fixa e UTF-8 sem BOM. Nenhuma
informacao de ambiente (host, data, PID) entra no arquivo, de modo que duas
execucoes produzem bytes identicos.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if not (BACKEND_ROOT / "app").is_dir():  # layout inesperado: mantem o repo root
    BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "api" / "openapi.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_schema() -> dict[str, object]:
    from app.core.config import Settings
    from app.main import create_app

    # Configuracao neutra: o contrato nao depende de banco, Redis ou busca.
    settings = Settings(
        environment="test",
        otel_enabled=False,
        elasticsearch_enabled=False,
        rate_limit_enabled=False,
    )
    app = create_app(settings)
    return app.openapi()


def render(schema: dict[str, object]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exporta o OpenAPI deterministico.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Nao grava; retorna 1 se o snapshot versionado estiver diferente.",
    )
    args = parser.parse_args(argv)

    rendered = render(build_schema())
    output: Path = args.output.resolve()

    if args.check:
        if not output.is_file():
            print(f"Snapshot ausente: {output}", file=sys.stderr)
            return 1
        current = output.read_text(encoding="utf-8")
        if current != rendered:
            print(
                "OpenAPI divergente do snapshot. Rode "
                "`python scripts/export_openapi.py` e revise o diff.",
                file=sys.stderr,
            )
            return 1
        print(f"OpenAPI deterministico e igual ao snapshot: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    print(f"OpenAPI exportado: {output} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
