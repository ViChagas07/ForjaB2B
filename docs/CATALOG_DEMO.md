# Fluxo de Demonstração do Catálogo — Fotos e Manifesto

Este documento descreve o processo para transformar fotos brutas em produtos publicáveis
no catálogo, usando o manifesto versionado como intermediário.

---

## Visão geral

1. **Entrada**: Fotos colocadas em `assets-src/` (pasta **não versionada**, no `.gitignore`).
2. **Processamento**: Script gera `backend/app/seed_data/catalog_photos_manifest.json`
   com rascunhos de produtos (um por foto).
3. **Revisão humana**: Responsável confere cada rascunho e preenche/ajusta campos.
4. **Publicação**: Apenas entradas com `owner_verified: true` e créditos completos
   podem ser promovidas a produtos reais no banco.

---

## Checklist do Responsável

Para **cada entrada** do manifesto, o responsável deve conferir:

### ✅ Licença e origem
- [ ] A foto tem licença compatível (ex.: Pexels License, Unsplash, CC0, ou autorização explícita).
- [ ] `source_url` aponta para a página original da foto.
- [ ] `author` está preenchido (quando aplicável).
- [ ] `license` e `license_url` estão corretos.

### ✅ Conteúdo da imagem
- [ ] **Sem rostos identificáveis** de pessoas reais.
- [ ] **Sem logotipos ou marcas visíveis** de terceiros (exceto marcas fictícias do seed).
- [ ] A imagem representa o produto descrito no `name`.

### ✅ Dados do produto
- [ ] `name`: Nome correto em pt-BR, acentuado, preposições minúsculas.
- [ ] `description`: 1–2 frases, até 200 chars, tom neutro de catálogo,
  descrevendo tipo e uso geral. **Sem** certificação, norma, CA, desempenho,
  potência, medidas, materiais, garantias.
- [ ] `category_slug`: Categoria existente mais coerente.
- [ ] `brand`: Marca fictícia do seed (nunca marca real).
- [ ] `list_price`: Dentro da faixa da categoria, arredondado como varejo.
- [ ] `sku`: Segue convenção `EPI-XXX-###` ou `MAQ-XXX-###`.

### ✅ Finalização
- [ ] Ajustar `needs_name` para `false` (se era `true`).
- [ ] Ajustar `needs_review` para `false` (se era `true`).
- [ ] Preencher `source_url`, `author`, `license`, `license_url` se faltando.
- [ ] Definir `owner_verified: true` **apenas após** todos os itens acima conferidos.

---

## Critérios de publicabilidade

Uma entrada é **publicável** (pode ser inserida no banco) se e somente se:

```text
owner_verified == true
AND needs_name == false
AND (source_url != null OR author != null)
```

A função `ManifestEntry.is_publishable()` encapsula esta regra.

---

## Como rodar

```bash
# 1. Colocar fotos em assets-src/ (jpg, jpeg, png, webp, avif)

# 2. Gerar/atualizar manifesto
cd backend
python -c "
from app.application.photo_manifest import generate_drafts_from_dir, save_manifest
from pathlib import Path
manifest = generate_drafts_from_dir(Path('../assets-src'))
save_manifest(manifest, Path('app/seed_data/catalog_photos_manifest.json'))
print(f'Geradas {len(manifest.entries)} entradas')
"

# 3. Editar o manifesto (JSON) conforme checklist acima

# 4. Validar
python -c "
from app.application.photo_manifest import load_manifest, validate_manifest
from pathlib import Path
manifest = load_manifest(Path('app/seed_data/catalog_photos_manifest.json'))
result = validate_manifest(manifest)
print(f'Válido: {result.valid}')
print(f'Erros: {len(result.errors)}')
print(f'Avisos: {len(result.warnings)}')
for w in result.warnings:
    print(f'  - {w}')
# Publicáveis:
print(f'Publicáveis: {len(manifest.get_publishable_entries())}')
"

# 5. (Futuro) Publicar no banco - fora do escopo desta fase
```

---

## Estrutura do Manifesto

```json
{
  "version": 1,
  "created_at": "2026-10-11T02:00:00+00:00",
  "updated_at": "2026-10-11T02:00:00+00:00",
  "entries": [
    {
      "source_file": "capacete.jpg",
      "sku": "EPI-CAP-001",
      "name": "Capacete de Segurança",
      "description": "Capacete para proteção da cabeça em ambientes industriais e de construção.",
      "category_slug": "protecao-cabeca",
      "brand": "protec",
      "list_price": "24.90",
      "needs_name": false,
      "needs_review": false,
      "brand_is_placeholder": true,
      "price_is_demo": true,
      "category_confidence": "alta",
      "name_source": "derivado do arquivo",
      "description_source": "gerada",
      "source_url": "https://www.pexels.com/photo/12345/",
      "author": "João Silva",
      "license": "Pexels License",
      "license_url": "https://www.pexels.com/license/",
      "downloaded_at": "2026-10-11T02:00:00+00:00",
      "attribution_text": "Foto por João Silva no Pexels",
      "modifications": "Recortado para foco no produto",
      "inferred_from_filename": true,
      "owner_verified": false
    }
  ]
}
```

---

## Campos obrigatórios para publicação

| Campo | Obrigatório | Notas |
|-------|-------------|-------|
| `source_file` | Sim | Nome do arquivo original |
| `sku` | Sim | Convenção do seed |
| `name` | Sim | pt-BR, acentuado |
| `description` | Sim | ≤200 chars, sem termos proibidos |
| `category_slug` | Sim | De `VALID_CATEGORIES` |
| `brand` | Sim | De `VALID_BRANDS` (fictícias) |
| `list_price` | Sim | Decimal > 0, 2 casas |
| `owner_verified` | Sim | **Deve ser `true`** |
| `needs_name` | Sim | Deve ser `false` |
| `source_url` ou `author` | Sim | Pelo menos um preenchido |

---

## Termos proibidos na descrição

Não use estes termos (nem variações com acento) na `description`:

- `certificado`, `certificação`, `norma`, `abnt`, `iso`
- `desempenho`, `potência`, `medida`, `material`, `garantia`
- `watt`, `volt`, `ampere`, `hp`, `cv`, `rpm`
- `mm`, `cm`, `kg`, `l`, `ml`, `bar`, `psi`, `db`, `hz`
- Padrão `CA-12345` (regex: `\bca-\d+\b`)

---

## Categorias válidas (slugs)

```
epis, protecao-cabeca, protecao-visual, protecao-maos,
protecao-respiratoria, protecao-auditiva, protecao-pes,
protecao-quedas, maquinas-e-ferramentas, ferramentas-eletricas,
maquinas-estacionarias
```

## Marcas válidas (slugs, todas fictícias)

```
protec, norton, vulcano, aegis, guardian, ferrum, titan, sentinel
```

---

## Notas importantes

- **Nunca** versionar a pasta `assets-src/` (originais).
- O manifesto é **versionado** em `backend/app/seed_data/`.
- O template vazio está em `catalog_photos_manifest_template.json`.
- Fotos com padrão Pexels (`pexels-autor-123.jpg`) ganham `needs_name: true`
  e créditos pré-preenchidos (`author`, `source_url`, `license`).
- Marcas são **sempre** placeholders fictícios do seed (`brand_is_placeholder: true`).
- Preços são **demonstração** (`price_is_demo: true`), dentro da faixa da categoria.
- A validação falha se houver erros estruturais; avisos (`warnings`) indicam
  entradas não publicáveis (ex.: `owner_verified: false`).

---

## Próximos passos (fora desta fase)

- Interface de admin para editar o manifesto.
- Botão "Publicar" que lê entradas publicáveis e insere no banco.
- Upload/otimização das imagens para CDN/storage.
- Geração de thumbnails e variantes.
---

## Fotos reais e ilustrações por produto (Prompt 10)

O catálogo exibe imagens em três níveis, por precedência:

1. **Foto real do produto** — `image_url = /catalog/photos/<sku-minúsculas>.webp`
   (servida pelo próprio frontend, pasta `frontend/public/catalog/photos/`).
2. **Ilustração SVG específica da família** — `image_url = /catalog/illustrations/<família>.svg`
   (`frontend/public/catalog/illustrations/`, mapa em `docs/illustrations/FAMILIES.md`).
3. **Ilustração padrão da categoria** — fallback automático em
   `backend/app/static/catalog/<categoria>.svg` (`resolve_product_image_path`).

A resolução no frontend (`shared/components/product-image-resolve.ts`):
`/static/...` vai para a origem da API; `/catalog/...` fica na origem do frontend;
`https://...` passa como está. O tipo visual deriva do prefixo: fotos em
`/catalog/photos/` usam `object-cover` (preenchem o quadro 1:1); ilustrações usam
`object-contain` (aparecem inteiras, sobre o próprio ladrilho escuro).

### Como adicionar uma NOVA FOTO de produto

1. Coloque o original (sem marca d'água, com crédito dedutível) e registre-o em
   `docs/illustrations/PHOTO_MAPPING.md` (arquivo → SKU, confiança, motivo).
2. Adicione a tupla `(arquivo, SKU, modo)` em `scripts/optimize_catalog_photos.py`
   (`crop` = recorte quadrado central; `fit` = composição em fundo neutro quando o
   recorte cortaria o objeto).
3. Rode `python scripts/optimize_catalog_photos.py` — gera 640×640 WebP ≤ 80 KB,
   **sem EXIF/GPS**, idempotente, em `frontend/public/catalog/photos/<sku>.webp`.
4. Confira com `python scripts/optimize_catalog_photos.py --verify`.
5. Mapeie o SKU → URL em `_PRODUCT_IMAGES` (`backend/app/infrastructure/db/seeds.py`)
   e rode o seed (idempotente).
6. Complete os créditos em `docs/IMAGE_CREDITS.md` (autor/source_url quando
   dedutível; `[PREENCHER]` caso contrário). Originais vão para
   `assets-src/photos-inbox/` (não versionado, não servido).

### Como adicionar uma NOVA ILUSTRAÇÃO de família

1. Crie `frontend/public/catalog/illustrations/<familia>.svg` no padrão duotone:
   `viewBox="0 0 512 512"`, ladrilho `rx≈96` `#0F172A`, traço branco `#F8FAFC`
   largura 14 com pontas/junções arredondadas, **um único** acento `#F97316`,
   `role="img"` + `<title>` em português, ≤ 3 KB, sem scripts/refs externas/texto.
2. Registre a família em `docs/illustrations/FAMILIES.md` (chave, SKUs, descrição).
3. Otimize: `npx svgo --multipass --config scripts/svgo.config.mjs -f
   frontend/public/catalog/illustrations` e depois, se o SVGO remover/corromper,
   `python scripts/fix_illustration_titles.py` e
   `python scripts/restore_illustration_role.py`.
4. Valide: `python scripts/validate_illustrations.py` (falha se violar o padrão ou
   se famílias/arquivos divergirem do FAMILIES.md).
5. Revise visualmente: `node frontend/scripts/rasterize-illustrations.mjs` (de
   `frontend/`; saída em `assets-src/render/`, ignorada) e a galeria
   `docs/illustrations/gallery.html`. Peça ajustes via
   `docs/illustrations/REVISIONS.md`.
6. Vincule o SKU em `_PRODUCT_IMAGES` e rode o seed. A foto sempre vence a
   ilustração; a ilustração da categoria é o último fallback.
