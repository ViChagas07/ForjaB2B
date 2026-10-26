"""Gera docs/illustrations/gallery.html (estatico, sem dependencias)."""

from pathlib import Path

root = Path(".")
illus = sorted((root / "frontend/public/catalog/illustrations").glob("*.svg"))
photos = sorted((root / "frontend/public/catalog/photos").glob("*.webp"))


def rel(p: Path) -> str:
    return "../../" + p.as_posix().replace("\\", "/")


cards: list[str] = []
for p in illus:
    name = p.stem
    src = rel(p)
    cards.append(
        f'<figure class="card" data-name="{name}">\n'
        f'<div class="row dark"><img src="{src}" width="96" height="96" alt="{name} 96px fundo escuro">'
        f'<img src="{src}" width="160" height="160" alt="{name} 160px fundo escuro">'
        f'<img src="{src}" width="320" height="320" alt="{name} 320px fundo escuro"></div>\n'
        f'<div class="row light"><img src="{src}" width="96" height="96" alt="{name} 96px fundo claro">'
        f'<img src="{src}" width="160" height="160" alt="{name} 160px fundo claro">'
        f'<img src="{src}" width="320" height="320" alt="{name} 320px fundo claro"></div>\n'
        f"<figcaption>{name} (ilustração)</figcaption>\n</figure>"
    )
for p in photos:
    name = p.stem
    src = rel(p)
    cards.append(
        f'<figure class="card" data-name="{name}">\n'
        f'<div class="row dark"><img src="{src}" width="96" height="96" alt="{name} 96px">'
        f'<img src="{src}" width="160" height="160" alt="{name} 160px">'
        f'<img src="{src}" width="320" height="320" alt="{name} 320px"></div>\n'
        f'<div class="row light"><img src="{src}" width="96" height="96" alt="{name} 96px claro">'
        f'<img src="{src}" width="160" height="160" alt="{name} 160px claro">'
        f'<img src="{src}" width="320" height="320" alt="{name} 320px claro"></div>\n'
        f"<figcaption>{name} (foto)</figcaption>\n</figure>"
    )

html = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Galeria de imagens do catalogo - Forja B2B (Prompt 10)</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 24px; background: #FAF9F6; color: #171717; }
  h1 { font-size: 20px; } p.hint { color: #666; font-size: 13px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }
  .card { margin: 0; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; background: #fff; }
  .row { display: flex; align-items: flex-end; gap: 12px; padding: 16px; }
  .row.dark { background: #0A0A0A; }
  .row.light { background: #FAF9F6; }
  img { display: block; }
  figcaption { padding: 10px 16px; font-size: 13px; font-weight: 600; border-top: 1px solid #eee; }
</style>
</head>
<body>
<h1>Galeria de revisao — fotos e ilustracoes do catalogo</h1>
<p class="hint">Ilustracoes (SVG duotone) e fotos (WebP) em 96, 160 e 320 px sobre fundo escuro e claro. Anote ajustes em REVISIONS.md.</p>
<div class="grid">
__CARDS__
</div>
</body>
</html>
""".replace("__CARDS__", "\n".join(cards))

out = root / "docs/illustrations/gallery.html"
out.write_text(html, encoding="utf-8")
print(f"gallery.html com {len(cards)} cartoes")
