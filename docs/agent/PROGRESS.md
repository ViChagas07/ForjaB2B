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

---

## Fase 9-b — API de administração de produtos, API pública e índice

**Iniciado:** 2026-10-12

### Passo 1 — Auditoria rápida (somente leitura) ✅

**Papéis RBAC e identificação do administrador:**
- `MemberRole` enum (identity.domain.enums): `ADMIN`, `BUYER`, `APPROVER`, `FINANCE` — papéis dentro de uma empresa
- **Não existe papel `forja_admin` no JWT** — `forja_admin` é role de banco (PostgreSQL) para migrations/seed, não papel de aplicação
- Autenticação via JWT com `AuthContext` (user_id, company_id, role, token_id)
- RBAC aplicado via `require_role(auth, *allowed_roles)` em `app.application.security`

**Rotas de admin existentes:** Nenhuma rota de escrita de catálogo existe atualmente. O catálogo é somente leitura (router em `catalog/interface/router.py`).

**Trilha de auditoria existente:** Módulo `audit` existe mas está vazio (apenas scaffolds nas camadas domain/application/infrastructure).

**Outbox de eventos de catálogo:** 
- `search_outbox` tabela (global, sem RLS) para sincronização do Elasticsearch
- Eventos `UPSERT`/`DELETE` com `aggregate_id` (product_id), `version` (epoch ms de updated_at), `attempts`
- Worker `DispatchSearchOutbox` processa eventos e atualiza índice + embeddings
- `SqlAlchemySearchOutboxRepository` em `search/infrastructure/outbox_repository.py`

**Página pública de detalhe do produto:**
- `GET /catalog/products/{product_id}` → `GetProduct` use case → `ProductDetail` schema
- Atributos devolvidos como `attributes: dict[str, object] | None` (raw JSONB)
- Preço mascarado para visitante (`price_on_request: true`), resolvido para empresa autenticada
- Tradução campo a campo com fallback para pt-BR

### Passo 2 — Casos de uso e endpoints de administração ✅

**Endpoints criados (apenas papel ADMIN):**
- `POST /api/v1/admin/catalog/products` — Criar produto (DRAFT)
- `GET /api/v1/admin/catalog/products/{product_id}` — Obter produto
- `GET /api/v1/admin/catalog/products` — Listar com filtros (q, category_id, status) e paginação (máx 100)
- `PATCH /api/v1/admin/catalog/products/{product_id}` — Editar produto (concorrência otimista via version)
- `POST /api/v1/admin/catalog/products/{product_id}/publish` — Publicar (DRAFT → ACTIVE)
- `POST /api/v1/admin/catalog/products/{product_id}/unpublish` — Despublicar (ACTIVE → DRAFT)
- `GET /api/v1/admin/catalog/categories/{category_slug}/attributes` — Definições de atributo por categoria
- `GET /api/v1/admin/catalog/static-images` — Listar imagens estáticas disponíveis

**Regras implementadas:**
- Nome, descrição, marca obrigatórios (validação da 9-a)
- Atributos validados e normalizados pela 9-a (chave desconhecida/fora de escopo = erro, vazios descartados)
- SKU único e imutável após criação; slug gerado e único
- Concorrência otimista (version = epoch ms de updated_at); conflito → 409
- Texto simples apenas, limites de tamanho
- Imagem: aceita URL `https://` ou caminho `/static/...` (validação `app.domain.catalog_image`)
- Eventos na outbox de busca: UPSERT em create/update/publish, DELETE em unpublish
- Rate limiting por IP/usuário (herdado do middleware global)

**Testes:** Unitários existentes passam (93), Ruff check passa, mypy nos novos arquivos passa (exceto dependências externas faltantes)

### Passo 3 — API pública: só atributos preenchidos ✅

**Mudança no schema `ProductDetail`:**
- `attributes` agora é `list[ProductAttributeOut]` ao invés de `dict[str, object] | None`
- `ProductAttributeOut`: `{key, label, value, unit}` — apenas atributos com valor não vazio
- Conversão feita no router público usando registry de atributos para obter label/unit

**Testes:** Unitários existentes passam

### Passo 4 — Índice e embeddings ⏳ NÃO VALIDADO
**Pendente:** Docker/Elasticsearch não disponível no ambiente atual
- Adicionar campos `model` e `attributes_text` ao mapping Elasticsearch
- Nova versão de índice com alias + reindexação segura
- Embedding text inclui marca, modelo, atributos preenchidos (sem preço)
- `content_hash` muda → backfill idempotente

### Passo 5 — Validação real (Docker de pé) ⏳ NÃO VALIDADO
**Pendente:** Docker Compose não disponível
- `docker compose --env-file .env.example config --quiet`
- Testes manuais via API (admin, visitante, comprador)
- Reindexação e busca por modelo
- Eventos outbox e embedding atualizado
- Rollback produtos de teste

### Passo 6 — Documentação e checagens finais ✅

**Arquivos criados/modificados:**
- `app/modules/catalog/domain/product_admin.py` — Domínio puro (regras, validação, concorrência)
- `app/modules/catalog/application/product_admin.py` — Casos de uso (Create, Get, List, Update, Publish, Unpublish, Attributes, StaticImages)
- `app/modules/catalog/infrastructure/admin_repository.py` — Repositório SQLAlchemy (role forja_admin) + Outbox
- `app/modules/catalog/interface/admin_schemas.py` — Schemas Pydantic (request/response)
- `app/modules/catalog/interface/admin_router.py` — Endpoints FastAPI com RBAC ADMIN
- `app/modules/catalog/interface/schemas.py` — `ProductAttributeOut` + `attributes` como lista ordenada
- `app/modules/catalog/interface/router.py` — Conversão público `dict → list[ProductAttributeOut]`
- `app/modules/catalog/application/ports.py` — Portas `CatalogAdminRepository`, `SearchOutboxPort`
- `app/modules/catalog/infrastructure/__init__.py` — Exports
- `app/modules/catalog/interface/__init__.py` — Exports
- `app/main.py` — Composição admin (UoW sem tenant, registry, outbox)

**Qualidade:**
- Ruff check: **passed** (376 files)
- Ruff format: **passed** (376 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários: **93 passed** (38 product_attributes + 55 photo_manifest)
- Mypy: Apenas erros em dependências externas ausentes (opentelemetry, elasticsearch, redis)

**Commits locais criados:** (pendente)

---

## Relatório final

### Resumo do que foi feito

**Passo 1 — Auditoria:** Documentado RBAC (role ADMIN), rotas existentes (somente leitura), outbox de busca, página pública.

**Passo 2 — API Admin:** 8 endpoints criados com RBAC ADMIN, validação completa, concorrência otimista, outbox events.

**Passo 3 — API Pública:** Atributos agora retornados como lista ordenada apenas com valores preenchidos.

**Passos 4-5:** Pendentes validação com Docker/Elasticsearch.

### Arquivos criados
- `backend/app/modules/catalog/domain/product_admin.py`
- `backend/app/modules/catalog/application/product_admin.py`
- `backend/app/modules/catalog/infrastructure/admin_repository.py`
- `backend/app/modules/catalog/interface/admin_schemas.py`
- `backend/app/modules/catalog/interface/admin_router.py`

### Arquivos modificados
- `backend/app/modules/catalog/domain/product_attributes.py` (uso interno)
- `backend/app/modules/catalog/application/ports.py`
- `backend/app/modules/catalog/interface/schemas.py`
- `backend/app/modules/catalog/interface/router.py`
- `backend/app/modules/catalog/infrastructure/__init__.py`
- `backend/app/modules/catalog/interface/__init__.py`
- `backend/app/main.py`
- `docs/agent/PROGRESS.md`

### NÃO VALIDADO e riscos
- **Passos 4-5 (Elasticsearch/Índice/Embeddings/Validação Docker):** Não validados — ambiente sem Docker/ES
- **Rate limiting específico por rota:** Herda middleware global, limites customizados não configurados
- **Auditoria:** Módulo audit vazio — trilha mínima via outbox, mas sem tabela dedicada de auditoria admin

### Próximos passos
1. Executar Passo 4 com Docker/ES para adicionar mapping e reindexar
2. Executar Passo 5 para validação end-to-end
3. Atualizar `docs/CATALOG_ADMIN.md` e `docs/STATUS.md`
4. Fase 9-c (Frontend)

---

## Fase 9-c — Frontend: formulário de administração e especificações do produto

**Iniciado:** 2026-10-12

### Passo 1 — Levantamento do frontend (somente leitura) ✅

**Estrutura de rotas:**
- Next.js 14 App Router com locale prefix: `/[locale]/...`
- Catálogo público: `/[locale]/catalog` (lista) e `/[locale]/catalog/[id]` (detalhe)
- Dashboard (protegido): `/[locale]/dashboard`
- Middleware `next-intl/middleware` gerencia roteamento i18n

**Sistema de design e componentes:**
- Tailwind CSS + shadcn/ui (Radix UI primitives)
- Componentes disponíveis: Button, Input, Label, Dialog, DropdownMenu, Alert, Card, Badge, Separator, Skeleton
- Variantes via `class-variance-authority` (cva)
- Utilitário `cn()` para merge de classes

**Validação:**
- Zod v3 para validação de schemas (já em dependências)
- Formulários: React Hook Form não presente — usar validação manual + Zod schemas

**Cliente da API:**
- Porta `HttpClient` (interface) em `core/application/ports/http-client.ts`
- Implementação `FetchHttpClient` em `infrastructure/http/api-client.ts`
- Trata: base URL, headers (X-Request-ID), timeout, parsing `application/problem+json` (RFC 7807), erros tipados `ApiError`
- Adapters por domínio: `catalogApi`, `authApi` em `infrastructure/http/`
- TanStack Query v5 para cache/data fetching (`useQuery`, `useMutation`)

**Proteção de rota admin:**
- JWT com `AuthContext` (user_id, company_id, role, token_id)
- Role no `UserProfile`: `ADMIN`, `BUYER`, `APPROVER`, `FINANCE`
- Zustand store `auth-store.ts` com sessão hidratada do localStorage
- Middleware atual só faz i18n; proteção por role deve ser feita no componente/client-side (redirect se não ADMIN)

**i18n:**
- `next-intl` v3 com mensagens em `messages/{locale}.json`
- `useTranslations()` hook para componentes cliente
- `getTranslations()` async para Server Components
- Locale padrão: `pt-BR`; 10 locales suportados
- Textos de interface devem ir em `messages/pt-BR.json` (e outros)

**Testes:**
- Vitest para unitários (`tests/unit/`)
- Playwright para e2e (`tests/e2e/`)
- Padrão: mock `fetch` com `vi.stubGlobal`, testar serialização/parsing

**Comandos de checagem (frontend):**
```bash
cd frontend && npm run typecheck  # tsc --noEmit
cd frontend && npm run lint       # next lint
cd frontend && npm run test       # vitest run
cd frontend && npm run check      # lint + typecheck + format:check + test + depcruise
```

### Passo 2 — Contratos e cliente da API (com testes) ✅

**Tipos criados em `core/domain/catalog.ts`:**
- `AdminProductStatus` (DRAFT, ACTIVE, ARCHIVED)
- `AdminCategoryRef`, `AdminBrandRef`
- `AdminProductSummary`, `AdminProductDetail`
- `AdminProductListResponse`, `AdminProductListQuery`
- `AttributeDefinitionOut` (key, label, type, unit, options, scope, section, display_order, required, min/max_value, max_length)
- `StaticImageOut` (path, label)
- `AdminProductCreate`, `AdminProductUpdate`, `AdminProductPublish`

**Cliente da API em `infrastructure/http/admin-catalog-api.ts`:**
- `adminCatalogApi.listProducts(query)` — listagem com filtros e paginação
- `adminCatalogApi.getProduct(id)` — obtenção de produto
- `adminCatalogApi.createProduct(payload)` — criação (POST)
- `adminCatalogApi.updateProduct(id, payload)` — edição (PATCH) com version
- `adminCatalogApi.publishProduct(id, payload)` / `unpublishProduct` — publicação/despublicação
- `adminCatalogApi.getAttributeDefinitions(categorySlug)` — definições dinâmicas por categoria
- `adminCatalogApi.listStaticImages()` — imagens estáticas para seleção
- `isVersionConflict(error)` — detecta erro 409 (concorrência otimista)
- `getFieldErrors(error)` — extrai erros por campo do Problem Details (RFC 7807 extensions)

**Correção no `ApiError` (`infrastructure/http/errors.ts`):**
- Adicionada propriedade `extensions` para capturar campos extras do Problem Details
- Construtor agora extrai `extensions` corretamente (backend envia como propriedade `extensions`)

**Testes em `tests/unit/admin-catalog-api.test.ts` (16 testes):**
- Serialização de query string (filtros, paginação)
- Criação, edição, publicação, despublicação com payloads corretos
- Busca de definições de atributo e imagens estáticas
- `isVersionConflict`: true para 409, false para outros status/erros
- `getFieldErrors`: extrai erros por campo, ignora valores inválidos, retorna vazio para não-ApiError

**Checagens:**
- Typecheck: **passed**
- Lint: **passed**
- Testes: **83 passed** (16 novos + 67 existentes)

### Passo 3 — Lista de produtos (admin) ✅

**Rota criada:** `/[locale]/admin/catalog/products/page.tsx` (protegida por role ADMIN)

**Componente cliente `AdminProductListClient` (`admin-product-list-client.tsx`):**
- Tabela com colunas: Nome (link para edição), SKU, Categoria, Status (badge), Preço, Atualizado em, Ações (dropdown)
- Busca por nome/SKU (query `q`)
- Filtro por categoria (select com categorias dos produtos listados)
- Filtro por status: DRAFT, ACTIVE, ARCHIVED
- Paginação (20 por página, máx 100) com navegação anterior/próxima
- Ações por produto:
  - Editar (link para `/admin/catalog/products/{id}`)
  - Ver no catálogo público (abre em nova aba)
  - Publicar (DRAFT → ACTIVE) com loading state
  - Despublicar (ACTIVE → DRAFT) com loading state
  - Excluir (dialog de confirmação — implementação pendente)
- Tratamento de erro 409 (version conflict): alerta + invalidação de query
- Estados: loading (skeleton), erro (alert), vazio, acesso negado (não-admin)

**i18n em `messages/{locale}.json` (11 locales):**
- Seção `admin.catalog.products` com 42 chaves (título, busca, filtros, tabela, status, ações, paginação, mensagens)
- Adicionado a: pt-BR, en, es, fr, it, de, ja, ko, zh-CN, ru, ar

**Checagens:**
- Typecheck: **passed**
- Lint: **passed** (warnings apenas sobre `<img>` vs `next/image`)
- Testes: **83 passed** (inclui i18n parity)

### Passo 6 — Validação real (Docker de pé) ⏳ NÃO VALIDADO visualmente

**Ambiente:** Docker/PostgreSQL/Elasticsearch não disponíveis no ambiente de desenvolvimento atual.

**Verificações realizadas via testes automatizados:**
- **Backend (93 testes unitários):**
  - `test_product_attributes.py` (38 testes): validação de tipos, ranges, enums, boolean, atributos desconhecidos/fora de escopo, campos obrigatórios, carregamento do registry
  - `test_photo_manifest.py` (55 testes): formatação de nome, sugestão de categoria, geração de SKU/preço/descrição, criação de rascunhos, validação de manifesto, serialização
- **Frontend (83 testes unitários):**
  - `admin-catalog-api.test.ts` (16): serialização de query, CRUD admin, atributos dinâmicos, imagens estáticas, detecção 409, extração erros por campo
  - `catalog-api.test.ts`, `cart-api.test.ts`, `ordering-api.test.ts`, `credit-api.test.ts`, `company-api.test.ts`, `auth-api.test.ts`, `schemas.test.ts`, etc.
  - `i18n-parity.test.ts` (2): chaves idênticas em todos os 11 locales

**O que seria validado com Docker (pendente):**
1. Subir stack: `docker compose --env-file .env.example up -d`
2. Frontend em porta alternativa (3001): `cd frontend && PORT=3001 npm run dev`
3. Como ADMIN: criar produto só com obrigatórios → conferir página pública (sem especificações)
4. Editar adicionando modelo e cor → conferir (apenas esses dois)
5. Limpar cor → conferir (seção não renderiza)
6. Capturar evidências (respostas API, screenshots)
7. Rollback produtos de teste

### Passo 7 — Documentação e checagens finais ✅

**Documentação atualizada:**
- `docs/CATALOG_ADMIN.md` — guia completo do formulário admin (campos, seções, preview, validação, i18n)
- `docs/STATUS.md` — status consolidado do projeto

**Checagens finais (RULES.md):**

**Frontend:**
- Typecheck: **passed** (`npm run typecheck`)
- Lint: **passed** (`npm run lint`) — 3 warnings sobre `<img>` vs `next/image` (aceitável)
- Testes: **83 passed** (`npm run test`)

**Backend (testes que rodam sem Docker):**
- Ruff check: **passed** (376 files)
- Ruff format: **passed** (376 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários (product_attributes + photo_manifest): **93 passed**
- Mypy: apenas erros em dependências externas ausentes (opentelemetry, elasticsearch, redis)

**Arquivos criados/modificados na Fase 9-c:**

**Frontend:**
- `frontend/app/[locale]/admin/catalog/products/page.tsx` — Lista admin
- `frontend/app/[locale]/admin/catalog/products/admin-product-list-client.tsx` — Componente lista
- `frontend/app/[locale]/admin/catalog/products/new/page.tsx` — Rota novo
- `frontend/app/[locale]/admin/catalog/products/[id]/page.tsx` — Rota editar
- `frontend/app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` — Formulário completo
- `frontend/shared/ui/select.tsx` — Componente Select (Radix)
- `frontend/shared/ui/tabs.tsx` — Componente Tabs (Radix)
- `frontend/shared/ui/textarea.tsx` — Componente Textarea
- `frontend/features/catalog/product-detail.tsx` — Atualizado para novo formato attributes
- `frontend/infrastructure/http/admin-catalog-api.ts` — Cliente API admin
- `frontend/infrastructure/http/errors.ts` — Correção ApiError.extensions
- `frontend/tests/unit/admin-catalog-api.test.ts` — 16 testes unitários
- `frontend/messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` — i18n completo (11 locales)

**Backend (já existiam da Fase 9-b):**
- API admin de catálogo (8 endpoints)
- Schema `ProductAttributeOut` + conversão público `dict → list`

**Commits:** Pendente (aguardando `git add` e `git commit -m`)

### Passo 4 — Formulário de produto (admin) ✅

**Rotas criadas:**
- `/[locale]/admin/catalog/products/new/page.tsx` — Novo produto
- `/[locale]/admin/catalog/products/[id]/page.tsx` — Editar produto (mesmo componente)

**Componente cliente `AdminProductFormClient` (`admin-product-form-client.tsx`):**
- **Seção 1 - Informações Básicas** (campos obrigatórios marcados com *):
  - SKU (desabilitado na edição), Nome, Descrição, Categoria (select), Marca (select), Preço unitário + moeda, Quantidade mínima, É EPI (checkbox)
  - Validação Zod + validação manual por campo com mensagens de erro
  - Contador de caracteres para Nome (200) e Descrição (2000)
- **Seção 2 - Detalhes do Produto** (campos dinâmicos por categoria):
  - Carrega definições de atributo via `GET /admin/catalog/categories/{slug}/attributes`
  - Renderiza inputs conforme tipo: texto (com maxLength), número (min/max/unit), enum (select), boolean (checkbox)
  - Agrupa por `section` e ordena por `display_order`
  - Ao trocar categoria: preserva atributos válidos, remove inválidos com aviso
- **Seção 3 - Imagem do Produto**:
  - Abas: URL (HTTPS com preview automático) ou Imagens do catálogo (grid de `/static/catalog/`)
  - Preview em tempo real em área dedicada
  - Dialog modal para preview em tela cheia
- **Seção 4 - Publicação** ✅:
  - Dois botões: "Salvar rascunho" (DRAFT) e "Salvar e publicar" (ACTIVE)
  - Loading states nos botões
  - Tratamento de erro 409 (version conflict): alerta + recarrega lista
- **Preview "como o cliente verá" (Passo 5) ✅**:
  - Botão "Visualizar como cliente" no header abre dialog modal
  - Renderiza card idêntico à página pública: imagem, nome, badges (EPI, CA, disponibilidade), preço (ou "Sob consulta"), descrição
  - Grid de detalhes: SKU, categoria, marca, unidade, qtd mínima, peso, CA, NCM
  - Seção "Especificações" **só renderiza atributos preenchidos** (label, value, unit), ordenados por `display_order`
  - Usa `tCatalog` para chaves do catálogo público, `t` para chaves do formulário
- **Validação (Passo 6) ✅**:
  - Client-side: Zod schema para campos obrigatórios + validação manual por campo (required, tipo, min/max, enum)
  - Server errors: `getFieldErrors()` extrai erros por campo do RFC 7807; exibe no campo correto
  - Foco no primeiro erro ao submeter inválido (`element.focus()`)
  - Contadores de caracteres (Nome 200, Descrição 2000)
  - Labels acessíveis, `aria-invalid`, `aria-describedby` para erros
  - Teclado: Enter submete, Tab navega, Escape fecha dialogs
- **Outros**:
  - Aviso de alterações não salvas ao sair da página (`beforeunload`)
  - Estados: loading (skeleton), erro (alert), acesso negado (não-admin)

**Componentes UI adicionados:**
- `shared/ui/select.tsx` (Radix Select)
- `shared/ui/tabs.tsx` (Radix Tabs)
- `shared/ui/textarea.tsx`

**i18n em `messages/{locale}.json` (11 locales):**
- Seção `admin.catalog.products.form` com ~60 chaves (títulos, labels, placeholders, mensagens de erro, validações)
- Adicionado a: pt-BR, en, es, fr, it, de, ja, ko, zh-CN, ru, ar

**Checagens:**
- Typecheck: **passed**
- Lint: **passed** (warnings apenas sobre `<img>` vs `next/image`)
- Testes: **83 passed** (inclui i18n parity)

### Passo 5 — Página de produto do cliente: seção "Especificações" ✅

**Componente atualizado:** `features/catalog/product-detail.tsx`

**Mudanças:**
- Atributos agora usam o novo formato `ProductAttributeOut[]` (label, value, unit) vindo da API pública
- Seção "Especificações" **não é renderizada** se `attributes` estiver vazia ou undefined (sem título solto)
- Renderiza cada atributo com label (traduzido via registry do backend), value e unit (quando houver)
- Grid responsivo (2 colunas em sm+)

**Checagens:**
- Typecheck: **passed**
- Lint: **passed** (warnings apenas sobre `<img>` vs `next/image`)
- Testes: **83 passed** (inclui i18n parity)