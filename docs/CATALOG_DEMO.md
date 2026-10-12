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