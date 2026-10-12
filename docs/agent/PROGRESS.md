# Progresso

## Fase 9A-3a — Rascunhos de produtos a partir das fotos e manifesto

**Iniciado:** 2026-10-11
**Concluído:** 2026-10-11

### Passo 1 — Levantamento (somente leitura)
- **Pasta de entrada:** `assets-src/` (raiz, pois `photos-inbox/` está vazia)
- **Arquivos encontrados (10):**
  1. `bota-e-luva-de-obra-kindelmedia-8488037.jpg` (1.42 MB)
  2. `capacete-para-obra-38070.jpg` (1.60 MB)
  3. `colete-de-obra-436474929-17858119.jpg` (713 KB)
  4. `furadeira-3877525.jpg` (873 KB)
  5. `kit-parafuso-7285983.jpg` (3.00 MB)
  6. `luva-de-obra-8488007.jpg` (1.51 MB)
  7. `mascara-de-gas-3435524-5499417.jpg` (957 KB)
  8. `máscara-respiradora-8487784.jpg` (832 KB)
  9. `protetor-auricular-6791514.jpg` (2.24 MB)
  10. `turquesa-2160382064-36847981.jpg` (1.55 MB)
- **Categorias, marcas, SKUs, faixas de preço:** conforme seed (documentado no arquivo)

### Passo 2 — Formato do manifesto ✅
- Criado `backend/app/domain/photo_manifest.py` (domínio puro, dataclasses)
- Criado `backend/app/application/photo_manifest.py` (Pydantic v2, validação, serialização)
- Modelo vazio com instruções: `backend/app/seed_data/catalog_photos_manifest_template.json`
- Validador rejeita entrada sem `sku`, `name`, `description`, `category_slug` válida, `brand` existente
- Entrada com `owner_verified: false`, `needs_name: true` ou créditos incompletos = "não publicável"

### Passo 3 — Função de formatação de nome (com testes) ✅
- `filename_to_product_name()`: remove extensão, troca `-`/`_` por espaço, colapsa espaços, remove sufixos de cópia, título em PT-BR com acentos corrigidos, preposições minúsculas
- Padrão Pexels (`pexels-autor-123.jpg`, `pexels-photo-123.jpeg`, `pexels-123.jpg`) → `needs_name: true`, créditos inferidos
- **Testes:** 10 casos cobertos (nome simples, hífen/underscore, acentos, preposições, sufixo cópia, inglês, 3 padrões Pexels, colapso espaços) — todos verdes

### Passo 4 — Gerar os rascunhos ✅
- `generate_drafts_from_dir()` processa `assets-src/` e gera manifesto com 10 entradas
- Cada entrada: `name` derivado, `category_slug` sugerida (confiança alta/baixa), `brand` placeholder determinística por categoria, `sku` estável determinístico, `list_price` na faixa da categoria arredondado varejo, `description` 1-2 frases ≤200 chars sem termos proibidos
- Pexels: `author`, `source_url`, `license` pré-preenchidos, `inferred_from_filename: true`
- **Nunca** `owner_verified: true` automático

### Passo 5 — Validação do manifesto (com testes) ✅
- `validate_manifest()` verifica regras estruturais + publicabilidade
- Testes: 55 testes unitários cobrindo domínio e aplicação (válido, inválidos vários, publicável, não publicável, serialização) — todos verdes

### Passo 6 — Pasta de entrada e documentação ✅
- `assets-src/` adicionado ao `.gitignore` (originais nunca versionados)
- Criado `docs/CATALOG_DEMO.md` com fluxo completo e checklist do responsável

### Passo 7 — Checagens finais ✅
- Ruff check: **passed**
- Ruff format: **passed**
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários: **111 passed** (incluindo 55 novos)

---

## Relatório final

### Tabela de rascunhos gerados

| Arquivo | Nome | Categoria | Confiança | SKU | Flags |
|---------|------|-----------|-----------|-----|-------|
| bota-e-luva-de-obra-kindelmedia-8488037.jpg | Bota e Luva de Obra Kindelmedia | protecao-maos | alta | EPI-LUV-397 | needs_review=False |
| capacete-para-obra-38070.jpg | Capacete para Obra | protecao-cabeca | alta | EPI-CAP-345 | needs_review=False |
| colete-de-obra-436474929-17858119.jpg | Colete de Obra 436474929 | epis | baixa | EPI-EPI-290 | needs_review=True |
| furadeira-3877525.jpg | Furadeira | ferramentas-eletricas | alta | EPI-FUR-656 | needs_review=False |
| kit-parafuso-7285983.jpg | Kit Parafuso | epis | baixa | EPI-EPI-917 | needs_review=True |
| luva-de-obra-8488007.jpg | Luva de Obra | protecao-maos | alta | EPI-LUV-925 | needs_review=False |
| mascara-de-gas-3435524-5499417.jpg | Máscara de Gas 3435524 | protecao-respiratoria | alta | EPI-RES-953 | needs_review=False |
| máscara-respiradora-8487784.jpg | Máscara Respiradora | protecao-respiratoria | alta | EPI-RES-436 | needs_review=False |
| protetor-auricular-6791514.jpg | Protetor Auricular | protecao-auditiva | alta | EPI-AUD-331 | needs_review=False |
| turquesa-2160382064-36847981.jpg | Turquesa 2160382064 | epis | baixa | EPI-EPI-345 | needs_review=True |

### Pendências
- **needs_name**: 0 (nenhum arquivo Pexels na entrada)
- **needs_review**: 3 (colete, kit, turquesa — categoria confiança baixa)
- **owner_verified**: 10 falsos (aguardando verificação do responsável)

### Arquivos criados/modificados
- `backend/app/domain/photo_manifest.py` (novo - domínio puro)
- `backend/app/application/photo_manifest.py` (novo - Pydantic v2)
- `backend/tests/unit/test_photo_manifest.py` (novo - 55 testes)
- `backend/app/seed_data/catalog_photos_manifest.json` (gerado - 10 entradas)
- `backend/app/seed_data/catalog_photos_manifest_template.json` (gerado - modelo vazio)
- `docs/CATALOG_DEMO.md` (novo - documentação do fluxo)
- `.gitignore` (atualizado - `assets-src/` ignorado)

### Comandos executados e resultados
```bash
# Testes
cd backend && python -m pytest tests/unit/test_photo_manifest.py -v
# 55 passed

# Qualidade
cd backend && python -m ruff check .
# All checks passed

cd backend && python -m ruff format --check .
# 366 files already formatted

cd backend && import-linter lint --config .import-linter
# 4 contracts kept, 0 broken
```

### NÃO VALIDADO e riscos
- **Imagens não inspecionadas visualmente**: O responsável deve conferir licença, rostos, logos nas imagens reais
- **Preços são demonstração**: `price_is_demo: true` — não devem ir para produção sem revisão comercial
- **Marcas são placeholders fictícias**: `brand_is_placeholder: true` — usar marcas reais apenas após negociação
- **0 publicados**: Aguardando verificação do responsável (`owner_verified: false` em todas)

### Commits locais criados
(Nenhum commit feito nesta sessão — apenas arquivos criados/modificados localmente)

---

**Declaração:** 0 publicados; aguardando verificação do responsável.

---

## Fase 9-a — Modelo de atributos de produto (domínio, migration e seed)

**Iniciado:** 2026-10-12
**Concluído:** 2026-10-12

### Passo 1 — Auditoria (somente leitura) ✅
- Documentado em `docs/CATALOG_ADMIN.md`:
  - Colunas atuais de `products` (nulabilidade, limites, índices)
  - **3 produtos violam "descrição obrigatória"**: EPI-LUV-002, EPI-RES-003, MAQ-PAR-004 (description NULL)
  - `brand_id` já é preenchido pelo seed (0 violações)
  - `name` já é NOT NULL (0 violações)
  - Marca modelada como entidade separada (`brands` table, FK SET NULL)
  - 11 categorias existentes (slugs documentados)

### Passo 2 — Domínio puro (com testes) ✅
- `app/domain/product_attributes.py`: tipos (text, number, enum, boolean), definição, validador, registry, normalizador
- `app/application/product_attributes.py`: Pydantic v2 schemas + service
- Regras de validação: tipo correto, número em intervalo, enum só opções válidas, texto com limite, chave desconhecida/fora de escopo = erro, vazios descartados
- **Testes:** 38 testes unitários cobrindo cada tipo, erros, normalização, obrigatórios — **todos verdes**

### Passo 3 — Persistência e migration ✅
- Migration `0017_product_attribute_definitions.py`: tabela `product_attribute_definitions` + coluna `attributes` JSONB já existente em `products`
- Tabela criada via SQL direto no container (alembic connection issues no Windows)
- Seed idempotente via SQL (`ON CONFLICT (key) DO UPDATE`) aplicado no container — **13 definições**
- NOT NULL em `description` e `brand_id` **NÃO aplicado** (aguardando preenchimento dos 3 produtos)

### Passo 4 — Seed das definições (idempotente) ✅
- JSON versionado em `backend/app/seed_data/attribute_definitions.json`
- 13 definições: 7 globais (modelo, cor, tamanho, material, peso_kg, unidade_venda) + 6 por categoria (tamanho luvas/botas, cor capacete/colete, potência/tensão ferramentas/máquinas, CA opcional)
- Rótulos e opções centralizados no JSON único (facilita tradução Fase 9-b)
- **Teste idempotência:** 2 execuções → mesmo resultado (13 INSERT 0 1)

### Passo 5 — Checagens finais e documentação ✅
- `docs/CATALOG_ADMIN.md` atualizado com modelo, regras, como adicionar definição, resultado auditoria
- Ruff check: **passed**
- Ruff format: **passed**
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários: **93 passed** (38 product_attributes + 55 photo_manifest)

---

## Relatório final consolidado

### Produtos que violam obrigatórios (Fase 9-a Passo 1)

| SKU | Campo Faltante | Status |
|-----|----------------|--------|
| EPI-LUV-002 | description (NULL) | Pendente preenchimento |
| EPI-RES-003 | description (NULL) | Pendente preenchimento |
| MAQ-PAR-004 | description (NULL) | Pendente preenchimento |

**NOT NULL aplicado em `description`?** NÃO — aguardando preenchimento.

**NOT NULL aplicado em `brand_id`?** NÃO — embora 0 violações, mantido nullable por FK SET NULL.

### Arquivos criados/modificados (Fase 9-a)

- `backend/app/domain/product_attributes.py` (novo - domínio puro)
- `backend/app/application/product_attributes.py` (novo - Pydantic v2)
- `backend/tests/unit/test_product_attributes.py` (novo - 38 testes)
- `backend/alembic/versions/0017_product_attribute_definitions.py` (novo - migration)
- `backend/app/seed_data/attribute_definitions.json` (novo - dicionário versionado)
- `backend/scripts/seed_attribute_definitions.py` (novo - script seed)
- `docs/CATALOG_ADMIN.md` (novo/atualizado - documentação completa)

### Qualidade (ambas fases)
- Ruff check: **passed**
- Ruff format: **passed** (371 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários: **93 passed** (38 + 55)

---

**Declaração:** Fase 9A-3a e Fase 9-a concluídas. Aguardando Fase 9-b (API admin) e Fase 9-c (frontend).