"""Restaura role=\"img\" nas raizes svg (one-off apos SVGO 4)."""

from pathlib import Path

count = 0
paths = list(Path("frontend/public/catalog/illustrations").glob("*.svg"))
paths += [
    Path("backend/app/static/catalog/protecao-respiratoria.svg"),
    Path("backend/app/static/catalog/protecao-maos.svg"),
]
for path in paths:
    text = path.read_text(encoding="utf-8")
    if 'role="img"' in text:
        continue
    old = 'viewBox="0 0 512 512">'
    new = 'viewBox="0 0 512 512" role="img">'
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        count += 1
    else:
        print(f"SEM MATCH: {path}")
print(f"role restaurado em {count} arquivos")
