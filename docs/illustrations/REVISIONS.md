# Revisões solicitadas (Prompt 10, Parte B4)

Responsável: anote abaixo o ajuste pedido por arquivo para uma segunda rodada.

Formato:

```
| Arquivo | O que mudar |
|---|---|
| `<familia>.svg` ou `<sku>.webp` | descrição do ajuste |
```

## Pendentes

(nenhum — primeira entrega)

## Instruções

- Galeria para revisão: `docs/illustrations/gallery.html` (abrir no navegador; mostra
  ilustrações e fotos em 96, 160 e 320 px sobre fundo escuro e claro).
- Fotos não aplicadas e suas opções: `docs/illustrations/PHOTO_MAPPING.md`.
- Após anotar, rode de novo o pipeline de ilustrações para a segunda rodada:
  editar o SVG → `npx svgo --multipass --config scripts/svgo.config.mjs -f frontend/public/catalog/illustrations`
  → `python scripts/fix_illustration_titles.py` → `python scripts/restore_illustration_role.py` (restaura
  títulos/`role` que o SVGO 4 pode remover/corromper no Windows) → `python scripts/validate_illustrations.py`
  → `node frontend/scripts/rasterize-illustrations.mjs` (de `frontend/`) para a revisão visual.
