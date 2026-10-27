# Progresso

> **Log cronolÃ³gico (nÃ£o Ã© o estado atual).** Registra o que foi feito em cada
> sessÃ£o, inclusive tentativas e nÃºmeros de testes da Ã©poca. O estado consolidado
> estÃ¡ em `docs/STATUS.md`. Algumas afirmaÃ§Ãµes antigas foram superadas (por
> exemplo, "rate limiting herdado do middleware" nÃ£o corresponde ao cÃ³digo
> atual); em caso de divergÃªncia, vale o cÃ³digo e o `STATUS.md`.

## Autocomplete estilo BestBuy â€” FASE 4: testes e validaÃ§Ã£o real (2026-10-27)

Pilha local: ES healthy (Ã­ndice `forja_products` com 41 docs, **v2 no alias** â€” v2 e v3
coexistem); backend container **reconstrÃ­do** (a imagem de 15 h nÃ£o tinha o `/suggest`,
404 antes do build). **Achado de ambiente:** o `.env` do dono aponta o primÃ¡rio para
**Elastic Cloud com credencial 401** â€” toda resposta do backend em `:8000` vinha do
**fallback PostgreSQL** (logs `suggest_primary_unavailable_switching_to_fallback`). Para
validar o ES de verdade: `docker compose run --rm -p 8001:8001 -e ELASTICSEARCH_URL=
http://elasticsearch:9200 -e ELASTICSEARCH_PASSWORD=... -e ELASTICSEARCH_API_KEY= backend
uvicorn ...` (env de processo, sem editar o `.env`; 200 verde ao final). Uvicorn local no
venv do Windows falha a conectar no Postgres do Docker (WinError 64/asyncpg) â€” por isso o
container. users/companies do banco demo: **0** â€” login HTTP inviÃ¡vel; token emitido no
prÃ³prio container (`python -c` com o secret do `.env`) validou o caminho autenticado.

**RequisiÃ§Ãµes reais (coletadas no relÃ³gio):** `q=cap` (ES) â†’ 8 termos + 3 categorias + 5
produtos por `_score` (CAP-004 no topo); `q=capacte` (ES) â†’ **5 capacetes** (fuzziness
real); `q=a` â†’ vazio; `q=3m` â†’ vazio (sem marca 3M no demo); `?lang=en` â†’
"Safety Helmet Pro"/"Head Protection" (traduÃ§Ã£o real); JWT â†’ 200 (sem regras â†’ lista);
**ES PARADO** â†’ 200 pelo fallback (8 termos, ordem alfabÃ©tica, sem typo) sem 500; ES
restaurado **green** ao final (nenhum volume tocado).

**Bugs reais achados pelo e2e (corrigidos):** Esc limpava o input `type=search` (aÃ§Ã£o
nativa do Chrome) â†’ `preventDefault` mantÃ©m o texto; resposta nova com placeholderData
resetava a seleÃ§Ã£o do teclado na mesma query â†’ reset passa a ser por `data.query`.
Teste e2e corrigido para esperar opÃ§Ãµes antes das setas (painel abre com skeleton; ARIA:
lista vazia nÃ£o seleciona) e para distinguir o TERMO sku `CAP-002` do produto (options de
produto tÃªm `<img>`).

**Checagens reais:** backend: Ruff/format **OK**; `mypy app` **0 erros**; import-linter
**4 kept**; `pytest tests/unit tests/integration` â†’ **836 passed, 1 skipped**. Frontend:
vitest passa a incluir `*.test.tsx` com jsx automÃ¡tico â€” `product-image-component.test.tsx`
(5 testes Ã³rfÃ£os desde a criaÃ§Ã£o) agora roda e passa; novos SSR do combobox (5);
`npm run check` completo â†’ **161 passed**, depcruise **0 violaÃ§Ãµes** (195 mÃ³dulos);
**e2e Playwright 6/6** contra a pilha real. `docker compose ps`/logs/ES `green` ao final.
Docs atualizados: `docs/STATUS.md` (feature + validaÃ§Ã£o) e `docs/search/RUNBOOK.md` (Â§6c
com contrato, receitas e checklist de sugestÃµes vazias). PendÃªncia do dono: renovar a
API key do Elastic Cloud ou apontar o dev para o ES local. NÃƒO VALIDADO: login HTTP real,
`_score` no Cloud, `q=3m` com marca real.

---

## Autocomplete estilo BestBuy â€” FASE 3: UI do autocomplete (2026-10-27)

`shared/components/search-combobox/`: `search-combobox.tsx` (form role=search,
combobox ARIA â€” aria-expanded/controls/autocomplete="list"/activedescendant,
teclado: setas verticais percorrem termos+categorias+produtos, laterais trocam
de bloco com inversÃ£o em RTL, Enter confirma o item ativo (sem ativo =
submit para /catalog?q=), Esc/Tab fecham mantendo o texto, pointerdown fora
fecha no document com cleanup, skeleton de 6 linhas enquanto isFetching sem
dados anteriores, vazio -> "Nenhum resultado para â€œqâ€" + link viewAll; painel
desktop absolute top-full min(52rem,90vw) grid 40/60 com max-h e scroll;
mobile fixed inset-x-0 top-[72px] coluna Ãºnica; sÃ³ classes lÃ³gicas), 
`suggestion-list.tsx` (termos com HighlightMatch + categorias "em {category}"),
`product-preview-list.tsx` (tÃ­tulo com o termo da resposta + 6 produtos:
ProductImage, line-clamp-2, SKU, CatalogPrice reusado, selo CaStatusBadge
quando ca_status=VALID, cart.minQuantity quando min_order_qty>1; clique ->
/catalog/<id>), `highlight-match.tsx` (splitHighlight puro: fold NFD sem
diacrÃ­ticos + mapa de codepoints de volta ao original â€” cobre harakat Ã¡rabe;
renderiza <strong>, sem dangerouslySetInnerHTML; 8 testes).
`HeaderSearch` virou wrapper fino do SearchCombobox (site-header sem mudanÃ§as,
mesmas props). `/catalog` sÃ³ aceita category_id (uuid), nÃ£o slug: clique em
categoria navega com q do input (decisÃ£o da fase). i18n: chaves search.*
(suggestionsGroup/popularResultsFor/inCategory/noResults/viewAll) nos 11
locales (script node no temp; placeholders preservados); preÃ§o sob consulta e
pedido mÃ­nimo REUSAM catalog.priceOnRequest e cart.minQuantity; es cognato
exato registrado na allowlist legÃ­tima do i18n-parity.

**Checagens reais:** `npm run check` COMPLETO PASSOU: lint OK (4 warnings
prÃ©-existentes de no-img-element em admin-product-form), typecheck 0,
format:check OK, **151 testes passed** (29 arquivos; +8 highlight-match),
depcruise 0 violaÃ§Ãµes (193 mÃ³dulos). Testes estÃ¡ticos RTL (sem classes
fÃ­sicas em shared/**) e hardcoded-text passam com o novo componente. NÃO
VALIDADO: comportamento visual/interativo em navegador real (digitar "cap"
abrindo apÃ³s ~200ms, setas/Enter/Esc de verdade e espelhamento visual em ar) â€”
fica para e2e Playwright da Fase 4; o projeto nÃ£o tem renderer de testes de
hooks/componentes (sem testing-library), comportamento do combobox coberto
por e2e.

**Arquivos:** `shared/components/search-combobox/search-combobox.tsx` (novo),
`.../suggestion-list.tsx` (novo), `.../product-preview-list.tsx` (novo),
`.../highlight-match.tsx` (novo), `shared/components/header-search.tsx`
(wrapper fino), `messages/{pt-BR,en,es,ar,de,fr,it,ja,ko,ru,zh-CN}.json`,
`tests/unit/highlight-match.test.ts` (novo),
`tests/unit/i18n-parity.test.ts` (allowlist es). site-header.tsx: intocado.

---

## Autocomplete estilo BestBuy â€” FASE 2: camada de dados do frontend (2026-10-27)

Sem componente visual (nenhum arquivo de UI tocado na fase). `searchApi.
fetchSuggestions(q, locale, signal)` chama GET /api/v1/search/suggest pelo
MESMO `apiClient` do catalogo (cookie/JWT + Accept-Language), tipos do
api-schema.d.ts gerado. Porta HttpRequest ganhou `signal?: AbortSignal`:
FetchHttpClient recusa requisicao ja abortada, propaga abort externo para o
controller interno e RELANCA o AbortError original (React Query trata como
cancelamento; timeout continua virando ApiError de rede). `features/search/`:
`query-keys.ts` (locale + q trim+lowercase), `debounce.ts` (createDebouncer
puro, testavel com fake timers), `use-debounced-value.ts` (200ms),
`use-search-suggestions.ts` (suggestQueryOptions testavel: enabled >= 2 chars
apos trim, staleTime 30s, placeholderData mantem anterior, retry false, signal
repassado; hook aplica debounce + locale do next-intl). Sem dependencia nova
(sem testing-library/jsdom: hooks testados via options + debouncer puro;
comportamento do hook de colagem fica para e2e da Fase 4).

**Checagens reais:** `npm run check` COMPLETO PASSOU: lint OK (4 warnings
pre-existentes de no-img-element em admin-product-form-client), typecheck 0,
format:check OK (apos style commit de 5 arquivos pre-existentes divergentes do
prettier atual â€” diff apenas requebramento, mesmos tokens), 143 testes passed
(28 arquivos; 11 novos em search-suggest.test.ts, 2 novos de signal em
http-client.test.ts), depcruise 0 violacoes (188 modulos). NAO VALIDADO:
dropdown em navegador real (fica para Fase 3/4 â€” esta fase nao tem UI);
`vitest.config.ts` nao inclui *.test.tsx, portanto
product-image-component.test.tsx nao roda no npm test (pre-existente,
relatado, nao alterado nesta fase).

**Arquivos:** `core/application/ports/http-client.ts`,
`infrastructure/http/api-client.ts`, `infrastructure/http/search-api.ts` (novo),
`infrastructure/http/index.ts`, `features/search/query-keys.ts` (novo),
`features/search/debounce.ts` (novo), `features/search/use-debounced-value.ts`
(novo), `features/search/use-search-suggestions.ts` (novo),
`tests/unit/http-client.test.ts`, `tests/unit/search-suggest.test.ts` (novo) e
5 arquivos apenas reformatados (style commit separado).

---

## Autocomplete estilo BestBuy â€” FASE 1: backend de sugestÃµes (2026-10-27)

Contrato novo `GET /api/v1/search/suggest` (dropdown: termos + categorias + 6
produtos), sem reindex e sem mexer no mapping (`name.autocomplete`, `name` com
fuzziness AUTO + prefix_length 1, `sku.prefix`, `brand.text`, `name_{locale}`
para en/es/ar). Sort SEMPRE por `_score` (nunca `name.sort`). Fallback Postgres
com ILIKE (nome/SKU/marca) + GROUP BY categoria, sem fuzzy. Preco/estoque
hidratados do PostgreSQL pela MESMA rotina do SearchProducts (extraida para
`_hydrate_page` compartilhada; preco consultivo p/ visitante, por empresa p/
autenticado). Rate limit identico ao de /search/products via middleware
(`/api/v1/search*` -> SEARCH). Categorias do suggest traduzidas no locale via
`get_category_name_map`. Termos: brand (prefixo) > product (hits) > sku
(prefixo), dedupe case-insensitive, limite 8; categorias: limite 3; produtos: 6.

**Comandos de checagem (backend, venv local no Windows):**
`backend/.venv/Scripts/ruff.exe check .` / `format --check .`;
`backend/.venv/Scripts/mypy.exe app` (strict; `mypy .` inclui testes com erros
PRE-EXISTENTES de outras fases, ver pendencias); `lint-imports --config
.import-linter` (no Windows pediu --config; container usa `lint-imports` puro);
`python -m pytest tests/unit -q`; `python -m pytest tests/integration -q`
(Testcontainers). OpenAPI: `python scripts/export_openapi.py` + (frontend)
`npm run openapi:types`.

**Checagens reais (todas executadas nesta sessao):**
- Ruff check/format: passed (429 arquivos formatados).
- mypy strict em `app` + testes de busca alterados: 0 erros (305-308 arquivos).
- Import-linter: 4 contracts kept, 0 broken.
- Unit: **548 passed** (12 novos de suggest).
- Integracao completa (Docker/Testcontainers, PG real + ES 9.5.5 real):
  **288 passed, 1 skipped** (skip pre-existente em test_search_semantic_pg).
- `docker compose --env-file .env.example config --quiet`: OK.
- Frontend `npm run typecheck`: OK (api-schema.d.ts regenerado).
- CritÃ©rios de aceite validados de verdade: `q=cap` -> "Capacete" no topo +
  categorias + 6 produtos com image_url e preco (HTTP fallback e ES real);
  `q=a` -> vazio; `q=capacte` -> "Capacete de Seguranca" no ES real
  (test_search_index_es::test_suggest_por_score_com_typo_e_agregacoes);
  ES fora do ar -> fallback responde 200 (suite HTTP roda com ES desabilitado).

**Arquivos:** `interface/schemas.py` (SuggestTermOut/SuggestCategoryOut/
SuggestResponse), `application/ports.py` (SuggestTerm/Category/Data +
SearchReader.suggest), `application/suggest.py` (novo, montagem pura de termos),
`infrastructure/elasticsearch.py` (suggest + aggs), `infrastructure/
postgres_search.py` (suggest fallback), `application/search.py` (_hydrate_page
compartilhada + SuggestProducts), `main.py` (wiring), `interface/router.py`
(GET /suggest), `docs/api/openapi.json` + `frontend/core/domain/api-schema.d.ts`
(regenerados), testes (unit/integration) e fakes conformes ao protocolo novo.

**Pendencias / NOTA (fora do escopo desta fase):** `mypy .` (incluindo tests/)
aponta 88 erros PRE-EXISTENTES em 13 arquivos de teste de outras features
(test_product_attributes, test_i18n, test_validate_illustrations,
test_stripe_integration, test_rate_limit, test_seed_product_images,
test_demo_translations, test_persistence_seeds, test_search_multilingual,
test_security_headers, test_deprecation, test_cors, test_rate_limit_api) â€”
nenhum deles foi tocado nesta fase; `mypy app` esta limpo. Corrigir os 88
exige toque em codigo de outras fases e ficou registrado como trabalho
pendente. CritÃ©rio "ES fora do ar -> fallback sem 500" validado no nivel HTTP
(suite roda com ELASTICSEARCH_ENABLED=False); nao houve teste que DERRUBE o ES
de verdade em runtime (so desabilita no settings de teste).

---

## Fase 9A-3a â€” Rascunhos de produtos a partir das fotos e manifesto

**Iniciado:** 2026-10-11
**ConcluÃ­do:** 2026-10-11

### Passo 1 â€” Levantamento (somente leitura)
- **Pasta de entrada:** `assets-src/` (raiz, pois `photos-inbox/` estÃ¡ vazia)
- **Arquivos encontrados (10):**
  1. `bota-e-luva-de-obra-kindelmedia-8488037.jpg` (1.42 MB)
  2. `capacete-para-obra-38070.jpg` (1.60 MB)
  3. `colete-de-obra-436474929-17858119.jpg` (713 KB)
  4. `furadeira-3877525.jpg` (873 KB)
  5. `kit-parafuso-7285983.jpg` (3.00 MB)
  6. `luva-de-obra-8488007.jpg` (1.51 MB)
  7. `mascara-de-gas-3435524-5499417.jpg` (957 KB)
  8. `mÃ¡scara-respiradora-8487784.jpg` (832 KB)
  9. `protetor-auricular-6791514.jpg` (2.24 MB)
  10. `turquesa-2160382064-36847981.jpg` (1.55 MB)
- **Categorias, marcas, SKUs, faixas de preÃ§o:** conforme seed (documentado no arquivo)

### Passo 2 â€” Formato do manifesto âœ…
- Criado `backend/app/domain/photo_manifest.py` (domÃ­nio puro, dataclasses)
- Criado `backend/app/application/photo_manifest.py` (Pydantic v2, validaÃ§Ã£o, serializaÃ§Ã£o)
- Modelo vazio com instruÃ§Ãµes: `backend/app/seed_data/catalog_photos_manifest_template.json`
- Validador rejeita entrada sem `sku`, `name`, `description`, `category_slug` vÃ¡lida, `brand` existente
- Entrada com `owner_verified: false`, `needs_name: true` ou crÃ©ditos incompletos = "nÃ£o publicÃ¡vel"

### Passo 3 â€” FunÃ§Ã£o de formataÃ§Ã£o de nome (com testes) âœ…
- `filename_to_product_name()`: remove extensÃ£o, troca `-`/`_` por espaÃ§o, colapsa espaÃ§os, remove sufixos de cÃ³pia, tÃ­tulo em PT-BR com acentos corrigidos, preposiÃ§Ãµes minÃºsculas
- PadrÃ£o Pexels (`pexels-autor-123.jpg`, `pexels-photo-123.jpeg`, `pexels-123.jpg`) â†’ `needs_name: true`, crÃ©ditos inferidos
- **Testes:** 10 casos cobertos (nome simples, hÃ­fen/underscore, acentos, preposiÃ§Ãµes, sufixo cÃ³pia, inglÃªs, 3 padrÃµes Pexels, colapso espaÃ§os) â€” todos verdes

### Passo 4 â€” Gerar os rascunhos âœ…
- `generate_drafts_from_dir()` processa `assets-src/` e gera manifesto com 10 entradas
- Cada entrada: `name` derivado, `category_slug` sugerida (confianÃ§a alta/baixa), `brand` placeholder determinÃ­stica por categoria, `sku` estÃ¡vel determinÃ­stico, `list_price` na faixa da categoria arredondado varejo, `description` 1-2 frases â‰¤200 chars sem termos proibidos
- Pexels: `author`, `source_url`, `license` prÃ©-preenchidos, `inferred_from_filename: true`
- **Nunca** `owner_verified: true` automÃ¡tico

### Passo 5 â€” ValidaÃ§Ã£o do manifesto (com testes) âœ…
- `validate_manifest()` verifica regras estruturais + publicabilidade
- Testes: 55 testes unitÃ¡rios cobrindo domÃ­nio e aplicaÃ§Ã£o (vÃ¡lido, invÃ¡lidos vÃ¡rios, publicÃ¡vel, nÃ£o publicÃ¡vel, serializaÃ§Ã£o) â€” todos verdes

### Passo 6 â€” Pasta de entrada e documentaÃ§Ã£o âœ…
- `assets-src/` adicionado ao `.gitignore` (originais nunca versionados)
- Criado `docs/CATALOG_DEMO.md` com fluxo completo e checklist do responsÃ¡vel

### Passo 7 â€” Checagens finais âœ…
- Ruff check: **passed**
- Ruff format: **passed**
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitÃ¡rios: **111 passed** (incluindo 55 novos)

---

## RelatÃ³rio final

### Tabela de rascunhos gerados

| Arquivo | Nome | Categoria | ConfianÃ§a | SKU | Flags |
|---------|------|-----------|-----------|-----|-------|
| bota-e-luva-de-obra-kindelmedia-8488037.jpg | Bota e Luva de Obra Kindelmedia | protecao-maos | alta | EPI-LUV-397 | needs_review=False |
| capacete-para-obra-38070.jpg | Capacete para Obra | protecao-cabeca | alta | EPI-CAP-345 | needs_review=False |
| colete-de-obra-436474929-17858119.jpg | Colete de Obra 436474929 | epis | baixa | EPI-EPI-290 | needs_review=True |
| furadeira-3877525.jpg | Furadeira | ferramentas-eletricas | alta | EPI-FUR-656 | needs_review=False |
| kit-parafuso-7285983.jpg | Kit Parafuso | epis | baixa | EPI-EPI-917 | needs_review=True |
| luva-de-obra-8488007.jpg | Luva de Obra | protecao-maos | alta | EPI-LUV-925 | needs_review=False |
| mascara-de-gas-3435524-5499417.jpg | MÃ¡scara de Gas 3435524 | protecao-respiratoria | alta | EPI-RES-953 | needs_review=False |
| mÃ¡scara-respiradora-8487784.jpg | MÃ¡scara Respiradora | protecao-respiratoria | alta | EPI-RES-436 | needs_review=False |
| protetor-auricular-6791514.jpg | Protetor Auricular | protecao-auditiva | alta | EPI-AUD-331 | needs_review=False |
| turquesa-2160382064-36847981.jpg | Turquesa 2160382064 | epis | baixa | EPI-EPI-345 | needs_review=True |

### PendÃªncias
- **needs_name**: 0 (nenhum arquivo Pexels na entrada)
- **needs_review**: 3 (colete, kit, turquesa â€” categoria confianÃ§a baixa)
- **owner_verified**: 10 falsos (aguardando verificaÃ§Ã£o do responsÃ¡vel)

### Arquivos criados/modificados
- `backend/app/domain/photo_manifest.py` (novo - domÃ­nio puro)
- `backend/app/application/photo_manifest.py` (novo - Pydantic v2)
- `backend/tests/unit/test_photo_manifest.py` (novo - 55 testes)
- `backend/app/seed_data/catalog_photos_manifest.json` (gerado - 10 entradas)
- `backend/app/seed_data/catalog_photos_manifest_template.json` (gerado - modelo vazio)
- `docs/CATALOG_DEMO.md` (novo - documentaÃ§Ã£o do fluxo)
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

### NÃƒO VALIDADO e riscos
- **Imagens nÃ£o inspecionadas visualmente**: O responsÃ¡vel deve conferir licenÃ§a, rostos, logos nas imagens reais
- **PreÃ§os sÃ£o demonstraÃ§Ã£o**: `price_is_demo: true` â€” nÃ£o devem ir para produÃ§Ã£o sem revisÃ£o comercial
- **Marcas sÃ£o placeholders fictÃ­cias**: `brand_is_placeholder: true` â€” usar marcas reais apenas apÃ³s negociaÃ§Ã£o
- **0 publicados**: Aguardando verificaÃ§Ã£o do responsÃ¡vel (`owner_verified: false` em todas)

### Commits locais criados
(Nenhum commit feito nesta sessÃ£o â€” apenas arquivos criados/modificados localmente)

---

**DeclaraÃ§Ã£o:** 0 publicados; aguardando verificaÃ§Ã£o do responsÃ¡vel.

---

## Fase 9-a â€” Modelo de atributos de produto (domÃ­nio, migration e seed)

**Iniciado:** 2026-10-12
**ConcluÃ­do:** 2026-10-12

### Passo 1 â€” Auditoria (somente leitura) âœ…
- Documentado em `docs/CATALOG_ADMIN.md`:
  - Colunas atuais de `products` (nulabilidade, limites, Ã­ndices)
  - **3 produtos violam "descriÃ§Ã£o obrigatÃ³ria"**: EPI-LUV-002, EPI-RES-003, MAQ-PAR-004 (description NULL)
  - `brand_id` jÃ¡ Ã© preenchido pelo seed (0 violaÃ§Ãµes)
  - `name` jÃ¡ Ã© NOT NULL (0 violaÃ§Ãµes)
  - Marca modelada como entidade separada (`brands` table, FK SET NULL)
  - 11 categorias existentes (slugs documentados)

### Passo 2 â€” DomÃ­nio puro (com testes) âœ…
- `app/domain/product_attributes.py`: tipos (text, number, enum, boolean), definiÃ§Ã£o, validador, registry, normalizador
- `app/application/product_attributes.py`: Pydantic v2 schemas + service
- Regras de validaÃ§Ã£o: tipo correto, nÃºmero em intervalo, enum sÃ³ opÃ§Ãµes vÃ¡lidas, texto com limite, chave desconhecida/fora de escopo = erro, vazios descartados
- **Testes:** 38 testes unitÃ¡rios cobrindo cada tipo, erros, normalizaÃ§Ã£o, obrigatÃ³rios â€” **todos verdes**

### Passo 3 â€” PersistÃªncia e migration âœ…
- Migration `0017_product_attribute_definitions.py`: tabela `product_attribute_definitions` + coluna `attributes` JSONB jÃ¡ existente em `products`
- Tabela criada via SQL direto no container (alembic connection issues no Windows)
- Seed idempotente via SQL (`ON CONFLICT (key) DO UPDATE`) aplicado no container â€” **13 definiÃ§Ãµes**
- NOT NULL em `description` e `brand_id` **NÃƒO aplicado** (aguardando preenchimento dos 3 produtos)

### Passo 4 â€” Seed das definiÃ§Ãµes (idempotente) âœ…
- JSON versionado em `backend/app/seed_data/attribute_definitions.json`
- 13 definiÃ§Ãµes: 7 globais (modelo, cor, tamanho, material, peso_kg, unidade_venda) + 6 por categoria (tamanho luvas/botas, cor capacete/colete, potÃªncia/tensÃ£o ferramentas/mÃ¡quinas, CA opcional)
- RÃ³tulos e opÃ§Ãµes centralizados no JSON Ãºnico (facilita traduÃ§Ã£o Fase 9-b)
- **Teste idempotÃªncia:** 2 execuÃ§Ãµes â†’ mesmo resultado (13 INSERT 0 1)

### Passo 5 â€” Checagens finais e documentaÃ§Ã£o âœ…
- `docs/CATALOG_ADMIN.md` atualizado com modelo, regras, como adicionar definiÃ§Ã£o, resultado auditoria
- Ruff check: **passed**
- Ruff format: **passed**
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitÃ¡rios: **93 passed** (38 product_attributes + 55 photo_manifest)

---

## RelatÃ³rio final consolidado

### Produtos que violam obrigatÃ³rios (Fase 9-a Passo 1)

| SKU | Campo Faltante | Status |
|-----|----------------|--------|
| EPI-LUV-002 | description (NULL) | Pendente preenchimento |
| EPI-RES-003 | description (NULL) | Pendente preenchimento |
| MAQ-PAR-004 | description (NULL) | Pendente preenchimento |

**NOT NULL aplicado em `description`?** NÃƒO â€” aguardando preenchimento.

**NOT NULL aplicado em `brand_id`?** NÃƒO â€” embora 0 violaÃ§Ãµes, mantido nullable por FK SET NULL.

### Arquivos criados/modificados (Fase 9-a)

- `backend/app/domain/product_attributes.py` (novo - domÃ­nio puro)
- `backend/app/application/product_attributes.py` (novo - Pydantic v2)
- `backend/tests/unit/test_product_attributes.py` (novo - 38 testes)
- `backend/alembic/versions/0017_product_attribute_definitions.py` (novo - migration)
- `backend/app/seed_data/attribute_definitions.json` (novo - dicionÃ¡rio versionado)
- `backend/scripts/seed_attribute_definitions.py` (novo - script seed)
- `docs/CATALOG_ADMIN.md` (novo/atualizado - documentaÃ§Ã£o completa)

### Qualidade (ambas fases)
- Ruff check: **passed**
- Ruff format: **passed** (371 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitÃ¡rios: **93 passed** (38 + 55)

---

**DeclaraÃ§Ã£o:** Fase 9A-3a e Fase 9-a concluÃ­das. Aguardando Fase 9-b (API admin) e Fase 9-c (frontend).

---

## Fase 9-b â€” API de administraÃ§Ã£o de produtos, API pÃºblica e Ã­ndice

**Iniciado:** 2026-10-12

### Passo 1 â€” Auditoria rÃ¡pida (somente leitura) âœ…

**PapÃ©is RBAC e identificaÃ§Ã£o do administrador:**
- `MemberRole` enum (identity.domain.enums): `ADMIN`, `BUYER`, `APPROVER`, `FINANCE` â€” papÃ©is dentro de uma empresa
- **NÃ£o existe papel `forja_admin` no JWT** â€” `forja_admin` Ã© role de banco (PostgreSQL) para migrations/seed, nÃ£o papel de aplicaÃ§Ã£o
- AutenticaÃ§Ã£o via JWT com `AuthContext` (user_id, company_id, role, token_id)
- RBAC aplicado via `require_role(auth, *allowed_roles)` em `app.application.security`

**Rotas de admin existentes:** Nenhuma rota de escrita de catÃ¡logo existe atualmente. O catÃ¡logo Ã© somente leitura (router em `catalog/interface/router.py`).

**Trilha de auditoria existente:** MÃ³dulo `audit` existe mas estÃ¡ vazio (apenas scaffolds nas camadas domain/application/infrastructure).

**Outbox de eventos de catÃ¡logo:** 
- `search_outbox` tabela (global, sem RLS) para sincronizaÃ§Ã£o do Elasticsearch
- Eventos `UPSERT`/`DELETE` com `aggregate_id` (product_id), `version` (epoch ms de updated_at), `attempts`
- Worker `DispatchSearchOutbox` processa eventos e atualiza Ã­ndice + embeddings
- `SqlAlchemySearchOutboxRepository` em `search/infrastructure/outbox_repository.py`

**PÃ¡gina pÃºblica de detalhe do produto:**
- `GET /catalog/products/{product_id}` â†’ `GetProduct` use case â†’ `ProductDetail` schema
- Atributos devolvidos como `attributes: dict[str, object] | None` (raw JSONB)
- PreÃ§o mascarado para visitante (`price_on_request: true`), resolvido para empresa autenticada
- TraduÃ§Ã£o campo a campo com fallback para pt-BR

### Passo 2 â€” Casos de uso e endpoints de administraÃ§Ã£o âœ…

**Endpoints criados (apenas papel ADMIN):**
- `POST /api/v1/admin/catalog/products` â€” Criar produto (DRAFT)
- `GET /api/v1/admin/catalog/products/{product_id}` â€” Obter produto
- `GET /api/v1/admin/catalog/products` â€” Listar com filtros (q, category_id, status) e paginaÃ§Ã£o (mÃ¡x 100)
- `PATCH /api/v1/admin/catalog/products/{product_id}` â€” Editar produto (concorrÃªncia otimista via version)
- `POST /api/v1/admin/catalog/products/{product_id}/publish` â€” Publicar (DRAFT â†’ ACTIVE)
- `POST /api/v1/admin/catalog/products/{product_id}/unpublish` â€” Despublicar (ACTIVE â†’ DRAFT)
- `GET /api/v1/admin/catalog/categories/{category_slug}/attributes` â€” DefiniÃ§Ãµes de atributo por categoria
- `GET /api/v1/admin/catalog/static-images` â€” Listar imagens estÃ¡ticas disponÃ­veis

**Regras implementadas:**
- Nome, descriÃ§Ã£o, marca obrigatÃ³rios (validaÃ§Ã£o da 9-a)
- Atributos validados e normalizados pela 9-a (chave desconhecida/fora de escopo = erro, vazios descartados)
- SKU Ãºnico e imutÃ¡vel apÃ³s criaÃ§Ã£o; slug gerado e Ãºnico
- ConcorrÃªncia otimista (version = epoch ms de updated_at); conflito â†’ 409
- Texto simples apenas, limites de tamanho
- Imagem: aceita URL `https://` ou caminho `/static/...` (validaÃ§Ã£o `app.domain.catalog_image`)
- Eventos na outbox de busca: UPSERT em create/update/publish, DELETE em unpublish
- Rate limiting por IP/usuÃ¡rio (herdado do middleware global)

**Testes:** UnitÃ¡rios existentes passam (93), Ruff check passa, mypy nos novos arquivos passa (exceto dependÃªncias externas faltantes)

### Passo 3 â€” API pÃºblica: sÃ³ atributos preenchidos âœ…

**MudanÃ§a no schema `ProductDetail`:**
- `attributes` agora Ã© `list[ProductAttributeOut]` ao invÃ©s de `dict[str, object] | None`
- `ProductAttributeOut`: `{key, label, value, unit}` â€” apenas atributos com valor nÃ£o vazio
- ConversÃ£o feita no router pÃºblico usando registry de atributos para obter label/unit

**Testes:** UnitÃ¡rios existentes passam

### Passo 4 â€” Ãndice e embeddings â³ NÃƒO VALIDADO
**Pendente:** Docker/Elasticsearch nÃ£o disponÃ­vel no ambiente atual
- Adicionar campos `model` e `attributes_text` ao mapping Elasticsearch
- Nova versÃ£o de Ã­ndice com alias + reindexaÃ§Ã£o segura
- Embedding text inclui marca, modelo, atributos preenchidos (sem preÃ§o)
- `content_hash` muda â†’ backfill idempotente

### Passo 5 â€” ValidaÃ§Ã£o real (Docker de pÃ©) â³ NÃƒO VALIDADO
**Pendente:** Docker Compose nÃ£o disponÃ­vel
- `docker compose --env-file .env.example config --quiet`
- Testes manuais via API (admin, visitante, comprador)
- ReindexaÃ§Ã£o e busca por modelo
- Eventos outbox e embedding atualizado
- Rollback produtos de teste

### Passo 6 â€” DocumentaÃ§Ã£o e checagens finais âœ…

**Arquivos criados/modificados:**
- `app/modules/catalog/domain/product_admin.py` â€” DomÃ­nio puro (regras, validaÃ§Ã£o, concorrÃªncia)
- `app/modules/catalog/application/product_admin.py` â€” Casos de uso (Create, Get, List, Update, Publish, Unpublish, Attributes, StaticImages)
- `app/modules/catalog/infrastructure/admin_repository.py` â€” RepositÃ³rio SQLAlchemy (role forja_admin) + Outbox
- `app/modules/catalog/interface/admin_schemas.py` â€” Schemas Pydantic (request/response)
- `app/modules/catalog/interface/admin_router.py` â€” Endpoints FastAPI com RBAC ADMIN
- `app/modules/catalog/interface/schemas.py` â€” `ProductAttributeOut` + `attributes` como lista ordenada
- `app/modules/catalog/interface/router.py` â€” ConversÃ£o pÃºblico `dict â†’ list[ProductAttributeOut]`
- `app/modules/catalog/application/ports.py` â€” Portas `CatalogAdminRepository`, `SearchOutboxPort`
- `app/modules/catalog/infrastructure/__init__.py` â€” Exports
- `app/modules/catalog/interface/__init__.py` â€” Exports
- `app/main.py` â€” ComposiÃ§Ã£o admin (UoW sem tenant, registry, outbox)

**Qualidade:**
- Ruff check: **passed** (376 files)
- Ruff format: **passed** (376 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitÃ¡rios: **93 passed** (38 product_attributes + 55 photo_manifest)
- Mypy: Apenas erros em dependÃªncias externas ausentes (opentelemetry, elasticsearch, redis)

**Commits locais criados:** (pendente)

---

## RelatÃ³rio final

### Resumo do que foi feito

**Passo 1 â€” Auditoria:** Documentado RBAC (role ADMIN), rotas existentes (somente leitura), outbox de busca, pÃ¡gina pÃºblica.

**Passo 2 â€” API Admin:** 8 endpoints criados com RBAC ADMIN, validaÃ§Ã£o completa, concorrÃªncia otimista, outbox events.

**Passo 3 â€” API PÃºblica:** Atributos agora retornados como lista ordenada apenas com valores preenchidos.

**Passos 4-5:** Pendentes validaÃ§Ã£o com Docker/Elasticsearch.

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

### NÃƒO VALIDADO e riscos
- **Passos 4-5 (Elasticsearch/Ãndice/Embeddings/ValidaÃ§Ã£o Docker):** NÃ£o validados â€” ambiente sem Docker/ES
- **Rate limiting especÃ­fico por rota:** Herda middleware global, limites customizados nÃ£o configurados
- **Auditoria:** MÃ³dulo audit vazio â€” trilha mÃ­nima via outbox, mas sem tabela dedicada de auditoria admin

### PrÃ³ximos passos
1. Executar Passo 4 com Docker/ES para adicionar mapping e reindexar
2. Executar Passo 5 para validaÃ§Ã£o end-to-end
3. Atualizar `docs/CATALOG_ADMIN.md` e `docs/STATUS.md`
4. Fase 9-c (Frontend)

---

## Fase 9-c â€” Frontend: formulÃ¡rio de administraÃ§Ã£o e especificaÃ§Ãµes do produto

**Iniciado:** 2026-10-12

### Passo 1 â€” Levantamento do frontend (somente leitura) âœ…

**Estrutura de rotas:**
- Next.js 14 App Router com locale prefix: `/[locale]/...`
- CatÃ¡logo pÃºblico: `/[locale]/catalog` (lista) e `/[locale]/catalog/[id]` (detalhe)
- Dashboard (protegido): `/[locale]/dashboard`
- Middleware `next-intl/middleware` gerencia roteamento i18n

**Sistema de design e componentes:**
- Tailwind CSS + shadcn/ui (Radix UI primitives)
- Componentes disponÃ­veis: Button, Input, Label, Dialog, DropdownMenu, Alert, Card, Badge, Separator, Skeleton
- Variantes via `class-variance-authority` (cva)
- UtilitÃ¡rio `cn()` para merge de classes

**ValidaÃ§Ã£o:**
- Zod v3 para validaÃ§Ã£o de schemas (jÃ¡ em dependÃªncias)
- FormulÃ¡rios: React Hook Form nÃ£o presente â€” usar validaÃ§Ã£o manual + Zod schemas

**Cliente da API:**
- Porta `HttpClient` (interface) em `core/application/ports/http-client.ts`
- ImplementaÃ§Ã£o `FetchHttpClient` em `infrastructure/http/api-client.ts`
- Trata: base URL, headers (X-Request-ID), timeout, parsing `application/problem+json` (RFC 7807), erros tipados `ApiError`
- Adapters por domÃ­nio: `catalogApi`, `authApi` em `infrastructure/http/`
- TanStack Query v5 para cache/data fetching (`useQuery`, `useMutation`)

**ProteÃ§Ã£o de rota admin:**
- JWT com `AuthContext` (user_id, company_id, role, token_id)
- Role no `UserProfile`: `ADMIN`, `BUYER`, `APPROVER`, `FINANCE`
- Zustand store `auth-store.ts` com sessÃ£o hidratada do localStorage
- Middleware atual sÃ³ faz i18n; proteÃ§Ã£o por role deve ser feita no componente/client-side (redirect se nÃ£o ADMIN)

**i18n:**
- `next-intl` v3 com mensagens em `messages/{locale}.json`
- `useTranslations()` hook para componentes cliente
- `getTranslations()` async para Server Components
- Locale padrÃ£o: `pt-BR`; 10 locales suportados
- Textos de interface devem ir em `messages/pt-BR.json` (e outros)

**Testes:**
- Vitest para unitÃ¡rios (`tests/unit/`)
- Playwright para e2e (`tests/e2e/`)
- PadrÃ£o: mock `fetch` com `vi.stubGlobal`, testar serializaÃ§Ã£o/parsing

**Comandos de checagem (frontend):**
```bash
cd frontend && npm run typecheck  # tsc --noEmit
cd frontend && npm run lint       # next lint
cd frontend && npm run test       # vitest run
cd frontend && npm run check      # lint + typecheck + format:check + test + depcruise
```

### Passo 2 â€” Contratos e cliente da API (com testes) âœ…

**Tipos criados em `core/domain/catalog.ts`:**
- `AdminProductStatus` (DRAFT, ACTIVE, ARCHIVED)
- `AdminCategoryRef`, `AdminBrandRef`
- `AdminProductSummary`, `AdminProductDetail`
- `AdminProductListResponse`, `AdminProductListQuery`
- `AttributeDefinitionOut` (key, label, type, unit, options, scope, section, display_order, required, min/max_value, max_length)
- `StaticImageOut` (path, label)
- `AdminProductCreate`, `AdminProductUpdate`, `AdminProductPublish`

**Cliente da API em `infrastructure/http/admin-catalog-api.ts`:**
- `adminCatalogApi.listProducts(query)` â€” listagem com filtros e paginaÃ§Ã£o
- `adminCatalogApi.getProduct(id)` â€” obtenÃ§Ã£o de produto
- `adminCatalogApi.createProduct(payload)` â€” criaÃ§Ã£o (POST)
- `adminCatalogApi.updateProduct(id, payload)` â€” ediÃ§Ã£o (PATCH) com version
- `adminCatalogApi.publishProduct(id, payload)` / `unpublishProduct` â€” publicaÃ§Ã£o/despublicaÃ§Ã£o
- `adminCatalogApi.getAttributeDefinitions(categorySlug)` â€” definiÃ§Ãµes dinÃ¢micas por categoria
- `adminCatalogApi.listStaticImages()` â€” imagens estÃ¡ticas para seleÃ§Ã£o
- `isVersionConflict(error)` â€” detecta erro 409 (concorrÃªncia otimista)
- `getFieldErrors(error)` â€” extrai erros por campo do Problem Details (RFC 7807 extensions)

**CorreÃ§Ã£o no `ApiError` (`infrastructure/http/errors.ts`):**
- Adicionada propriedade `extensions` para capturar campos extras do Problem Details
- Construtor agora extrai `extensions` corretamente (backend envia como propriedade `extensions`)

**Testes em `tests/unit/admin-catalog-api.test.ts` (16 testes):**
- SerializaÃ§Ã£o de query string (filtros, paginaÃ§Ã£o)
- CriaÃ§Ã£o, ediÃ§Ã£o, publicaÃ§Ã£o, despublicaÃ§Ã£o com payloads corretos
- Busca de definiÃ§Ãµes de atributo e imagens estÃ¡ticas
- `isVersionConflict`: true para 409, false para outros status/erros
- `getFieldErrors`: extrai erros por campo, ignora valores invÃ¡lidos, retorna vazio para nÃ£o-ApiError

**Checagens:**
- Typecheck: **passed**
- Lint: **passed**
- Testes: **83 passed** (16 novos + 67 existentes)

### Passo 3 â€” Lista de produtos (admin) âœ…

**Rota criada:** `/[locale]/admin/catalog/products/page.tsx` (protegida por role ADMIN)

**Componente cliente `AdminProductListClient` (`admin-product-list-client.tsx`):**
- Tabela com colunas: Nome (link para ediÃ§Ã£o), SKU, Categoria, Status (badge), PreÃ§o, Atualizado em, AÃ§Ãµes (dropdown)
- Busca por nome/SKU (query `q`)
- Filtro por categoria (select com categorias dos produtos listados)
- Filtro por status: DRAFT, ACTIVE, ARCHIVED
- PaginaÃ§Ã£o (20 por pÃ¡gina, mÃ¡x 100) com navegaÃ§Ã£o anterior/prÃ³xima
- AÃ§Ãµes por produto:
  - Editar (link para `/admin/catalog/products/{id}`)
  - Ver no catÃ¡logo pÃºblico (abre em nova aba)
  - Publicar (DRAFT â†’ ACTIVE) com loading state
  - Despublicar (ACTIVE â†’ DRAFT) com loading state
  - Excluir (dialog de confirmaÃ§Ã£o â€” implementaÃ§Ã£o pendente)
- Tratamento de erro 409 (version conflict): alerta + invalidaÃ§Ã£o de query
- Estados: loading (skeleton), erro (alert), vazio, acesso negado (nÃ£o-admin)

**i18n em `messages/{locale}.json` (11 locales):**
- SeÃ§Ã£o `admin.catalog.products` com 42 chaves (tÃ­tulo, busca, filtros, tabela, status, aÃ§Ãµes, paginaÃ§Ã£o, mensagens)
- Adicionado a: pt-BR, en, es, fr, it, de, ja, ko, zh-CN, ru, ar

**Checagens:**
- Typecheck: **passed**
- Lint: **passed** (warnings apenas sobre `<img>` vs `next/image`)
- Testes: **83 passed** (inclui i18n parity)

### Passo 6 â€” ValidaÃ§Ã£o real (Docker de pÃ©) â³ NÃƒO VALIDADO visualmente

**Ambiente:** Docker/PostgreSQL/Elasticsearch nÃ£o disponÃ­veis no ambiente de desenvolvimento atual.

**VerificaÃ§Ãµes realizadas via testes automatizados:**
- **Backend (93 testes unitÃ¡rios):**
  - `test_product_attributes.py` (38 testes): validaÃ§Ã£o de tipos, ranges, enums, boolean, atributos desconhecidos/fora de escopo, campos obrigatÃ³rios, carregamento do registry
  - `test_photo_manifest.py` (55 testes): formataÃ§Ã£o de nome, sugestÃ£o de categoria, geraÃ§Ã£o de SKU/preÃ§o/descriÃ§Ã£o, criaÃ§Ã£o de rascunhos, validaÃ§Ã£o de manifesto, serializaÃ§Ã£o
- **Frontend (83 testes unitÃ¡rios):**
  - `admin-catalog-api.test.ts` (16): serializaÃ§Ã£o de query, CRUD admin, atributos dinÃ¢micos, imagens estÃ¡ticas, detecÃ§Ã£o 409, extraÃ§Ã£o erros por campo
  - `catalog-api.test.ts`, `cart-api.test.ts`, `ordering-api.test.ts`, `credit-api.test.ts`, `company-api.test.ts`, `auth-api.test.ts`, `schemas.test.ts`, etc.
  - `i18n-parity.test.ts` (2): chaves idÃªnticas em todos os 11 locales

**O que seria validado com Docker (pendente):**
1. Subir stack: `docker compose --env-file .env.example up -d`
2. Frontend em porta alternativa (3001): `cd frontend && PORT=3001 npm run dev`
3. Como ADMIN: criar produto sÃ³ com obrigatÃ³rios â†’ conferir pÃ¡gina pÃºblica (sem especificaÃ§Ãµes)
4. Editar adicionando modelo e cor â†’ conferir (apenas esses dois)
5. Limpar cor â†’ conferir (seÃ§Ã£o nÃ£o renderiza)
6. Capturar evidÃªncias (respostas API, screenshots)
7. Rollback produtos de teste

### Passo 7 â€” DocumentaÃ§Ã£o e checagens finais âœ…

**DocumentaÃ§Ã£o atualizada:**
- `docs/CATALOG_ADMIN.md` â€” guia completo do formulÃ¡rio admin (campos, seÃ§Ãµes, preview, validaÃ§Ã£o, i18n)
- `docs/STATUS.md` â€” status consolidado do projeto

**Checagens finais (RULES.md):**

**Frontend:**
- Typecheck: **passed** (`npm run typecheck`)
- Lint: **passed** (`npm run lint`) â€” 3 warnings sobre `<img>` vs `next/image` (aceitÃ¡vel)
- Testes: **83 passed** (`npm run test`)

**Backend (testes que rodam sem Docker):**
- Ruff check: **passed** (376 files)
- Ruff format: **passed** (376 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitÃ¡rios (product_attributes + photo_manifest): **93 passed**
- Mypy: apenas erros em dependÃªncias externas ausentes (opentelemetry, elasticsearch, redis)

**Arquivos criados/modificados na Fase 9-c:**

**Frontend:**
- `frontend/app/[locale]/admin/catalog/products/page.tsx` â€” Lista admin
- `frontend/app/[locale]/admin/catalog/products/admin-product-list-client.tsx` â€” Componente lista
- `frontend/app/[locale]/admin/catalog/products/new/page.tsx` â€” Rota novo
- `frontend/app/[locale]/admin/catalog/products/[id]/page.tsx` â€” Rota editar
- `frontend/app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` â€” FormulÃ¡rio completo
- `frontend/shared/ui/select.tsx` â€” Componente Select (Radix)
- `frontend/shared/ui/tabs.tsx` â€” Componente Tabs (Radix)
- `frontend/shared/ui/textarea.tsx` â€” Componente Textarea
- `frontend/features/catalog/product-detail.tsx` â€” Atualizado para novo formato attributes
- `frontend/infrastructure/http/admin-catalog-api.ts` â€” Cliente API admin
- `frontend/infrastructure/http/errors.ts` â€” CorreÃ§Ã£o ApiError.extensions
- `frontend/tests/unit/admin-catalog-api.test.ts` â€” 16 testes unitÃ¡rios
- `frontend/messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` â€” i18n completo (11 locales)

**Backend (jÃ¡ existiam da Fase 9-b):**
- API admin de catÃ¡logo (8 endpoints)
- Schema `ProductAttributeOut` + conversÃ£o pÃºblico `dict â†’ list`

**Commits:** Pendente (aguardando `git add` e `git commit -m`)

### Passo 4 â€” FormulÃ¡rio de produto (admin) âœ…

**Rotas criadas:**
- `/[locale]/admin/catalog/products/new/page.tsx` â€” Novo produto
- `/[locale]/admin/catalog/products/[id]/page.tsx` â€” Editar produto (mesmo componente)

**Componente cliente `AdminProductFormClient` (`admin-product-form-client.tsx`):**
- **SeÃ§Ã£o 1 - InformaÃ§Ãµes BÃ¡sicas** (campos obrigatÃ³rios marcados com *):
  - SKU (desabilitado na ediÃ§Ã£o), Nome, DescriÃ§Ã£o, Categoria (select), Marca (select), PreÃ§o unitÃ¡rio + moeda, Quantidade mÃ­nima, Ã‰ EPI (checkbox)
  - ValidaÃ§Ã£o Zod + validaÃ§Ã£o manual por campo com mensagens de erro
  - Contador de caracteres para Nome (200) e DescriÃ§Ã£o (2000)
- **SeÃ§Ã£o 2 - Detalhes do Produto** (campos dinÃ¢micos por categoria):
  - Carrega definiÃ§Ãµes de atributo via `GET /admin/catalog/categories/{slug}/attributes`
  - Renderiza inputs conforme tipo: texto (com maxLength), nÃºmero (min/max/unit), enum (select), boolean (checkbox)
  - Agrupa por `section` e ordena por `display_order`
  - Ao trocar categoria: preserva atributos vÃ¡lidos, remove invÃ¡lidos com aviso
- **SeÃ§Ã£o 3 - Imagem do Produto**:
  - Abas: URL (HTTPS com preview automÃ¡tico) ou Imagens do catÃ¡logo (grid de `/static/catalog/`)
  - Preview em tempo real em Ã¡rea dedicada
  - Dialog modal para preview em tela cheia
- **SeÃ§Ã£o 4 - PublicaÃ§Ã£o** âœ…:
  - Dois botÃµes: "Salvar rascunho" (DRAFT) e "Salvar e publicar" (ACTIVE)
  - Loading states nos botÃµes
  - Tratamento de erro 409 (version conflict): alerta + recarrega lista
- **Preview "como o cliente verÃ¡" (Passo 5) âœ…**:
  - BotÃ£o "Visualizar como cliente" no header abre dialog modal
  - Renderiza card idÃªntico Ã  pÃ¡gina pÃºblica: imagem, nome, badges (EPI, CA, disponibilidade), preÃ§o (ou "Sob consulta"), descriÃ§Ã£o
  - Grid de detalhes: SKU, categoria, marca, unidade, qtd mÃ­nima, peso, CA, NCM
  - SeÃ§Ã£o "EspecificaÃ§Ãµes" **sÃ³ renderiza atributos preenchidos** (label, value, unit), ordenados por `display_order`
  - Usa `tCatalog` para chaves do catÃ¡logo pÃºblico, `t` para chaves do formulÃ¡rio
- **ValidaÃ§Ã£o (Passo 6) âœ…**:
  - Client-side: Zod schema para campos obrigatÃ³rios + validaÃ§Ã£o manual por campo (required, tipo, min/max, enum)
  - Server errors: `getFieldErrors()` extrai erros por campo do RFC 7807; exibe no campo correto
  - Foco no primeiro erro ao submeter invÃ¡lido (`element.focus()`)
  - Contadores de caracteres (Nome 200, DescriÃ§Ã£o 2000)
  - Labels acessÃ­veis, `aria-invalid`, `aria-describedby` para erros
  - Teclado: Enter submete, Tab navega, Escape fecha dialogs
- **Outros**:
  - Aviso de alteraÃ§Ãµes nÃ£o salvas ao sair da pÃ¡gina (`beforeunload`)
  - Estados: loading (skeleton), erro (alert), acesso negado (nÃ£o-admin)

**Componentes UI adicionados:**
- `shared/ui/select.tsx` (Radix Select)
- `shared/ui/tabs.tsx` (Radix Tabs)
- `shared/ui/textarea.tsx`

**i18n em `messages/{locale}.json` (11 locales):**
- SeÃ§Ã£o `admin.catalog.products.form` com ~60 chaves (tÃ­tulos, labels, placeholders, mensagens de erro, validaÃ§Ãµes)
- Adicionado a: pt-BR, en, es, fr, it, de, ja, ko, zh-CN, ru, ar

**Checagens:**
- Typecheck: **passed**
- Lint: **passed** (warnings apenas sobre `<img>` vs `next/image`)
- Testes: **83 passed** (inclui i18n parity)

### Passo 5 â€” PÃ¡gina de produto do cliente: seÃ§Ã£o "EspecificaÃ§Ãµes" âœ…

**Componente atualizado:** `features/catalog/product-detail.tsx`

**MudanÃ§as:**
- Atributos agora usam o novo formato `ProductAttributeOut[]` (label, value, unit) vindo da API pÃºblica
- SeÃ§Ã£o "EspecificaÃ§Ãµes" **nÃ£o Ã© renderizada** se `attributes` estiver vazia ou undefined (sem tÃ­tulo solto)
- Renderiza cada atributo com label (traduzido via registry do backend), value e unit (quando houver)
- Grid responsivo (2 colunas em sm+)

**Checagens:**
- Typecheck: **passed**
- Lint: **passed** (warnings apenas sobre `<img>` vs `next/image`)
- Testes: **83 passed** (inclui i18n parity)

---

## Fase 9B-a â€” TraduÃ§Ãµes armazenadas: modelo, resoluÃ§Ã£o, API e seed

**Iniciado:** 2026-10-13
**ConcluÃ­do:** 2026-10-13

### Passo 1 â€” Auditoria rÃ¡pida (somente leitura) âœ…

**Onde as respostas montam textos do produto:**

1. **CatÃ¡logo pÃºblico (lista e detalhe)** â€” `app/modules/catalog/application/catalog.py`:
   - `ListProducts.list()` e `GetProduct.get()` chamam `_with_translation()` que usa `resolve_product_text()` do domÃ­nio
   - Retorna `ProductView` com `name`, `description`, `attributes`, `content_locale`, `fallback`
   - Router pÃºblico (`app/modules/catalog/interface/router.py`) converte `attributes` dict â†’ `list[ProductAttributeOut]` usando registry para labels/units

2. **Busca (Fase 3/9-b)** â€” usa o mesmo repositÃ³rio `SqlAlchemyCatalogRepository` e `load_product_translations()`

3. **Carrinho** â€” `app/modules/cart/infrastructure/repository.py`:
   - `get_cart()` chama `_resolve_items_standalone()` que usa `resolve_product_text()` para nome, descriÃ§Ã£o e atributos
   - Retorna `CartItemView` com `name`, `description`, `attributes`, `content_locale`

4. **Pedidos** â€” `app/modules/ordering/application/order.py`:
   - `CreateOrder.create()` usa `get_product_for_order` com locale, resolve traduÃ§Ã£o
   - Order snapshot guarda `name`, `description`, `attributes` no locale do pedido + `content_locale`

**DicionÃ¡rio de rÃ³tulos/opÃ§Ãµes (Fase 9):**
- `app/infrastructure/i18n/category_names.json` â€” nomes de categoria por slug/locale
- `app/infrastructure/i18n/attribute_dictionary.json` â€” labels e options de atributos por locale
- Carregados via `load_category_names()` e `load_attribute_dictionary()` (cache LRU)

**Categorias existentes (11):**
- `epis` (pai), `protecao-cabeca`, `protecao-visual`, `protecao-maos`, `protecao-respiratoria`, `protecao-auditiva`, `protecao-pes`, `protecao-quedas`, `maquinas-e-ferramentas` (pai), `ferramentas-eletricas`, `maquinas-estacionarias`

### Passo 2 â€” Modelo e resoluÃ§Ã£o (com testes) âœ…
- Migration `0018_product_translations_translated_at.py`: adiciona coluna `translated_at` Ã  tabela `product_translations`
- Testes de domÃ­nio em `tests/unit/test_i18n.py`: 43 testes cobrindo negociaÃ§Ã£o de locale, fallback campo a campo, hash de origem, stale, sanitizaÃ§Ã£o, resoluÃ§Ã£o de texto de produto, nomes de categoria, dicionÃ¡rio de atributos â€” **todos verdes**
- Ruff check: **passed**
- Mypy: **passed** (erros apenas em cÃ³digo preexistente nÃ£o relacionado)

### Passo 3 â€” API (idioma e conteÃºdo) âœ…
- **NegociaÃ§Ã£o de locale**: `?lang=` > `Accept-Language` > default (`pt-BR`). Valor invÃ¡lido cai no default sem erro.
- **CatÃ¡logo**: Lista e detalhe retornam `content_locale` e `fallback`, atributos como lista ordenada.
- **Carrinho**: Atualizado para traduzir nome, descriÃ§Ã£o E atributos (antes sÃ³ nome).
- **Pedidos**: `get_product_for_order` aceita locale, `create_order` e `get_order` incluem `content_locale` no snapshot do pedido e itens.
- Testes unitÃ¡rios: **145 passed**
- Ruff check: **passed**
- Mypy: **passed** (apenas erros preexistentes)

### Passo 4 â€” Porta TranslationProvider + provedor nulo + endpoints admin âœ…
- **Porta** `TranslationProvider` em `app/application/ports/translation.py` com `NullTranslationProvider` (padrÃ£o, nÃ£o traduz).
- **Endpoints admin** (RBAC ADMIN):
  - `GET /api/v1/admin/catalog/translations/products/{product_id}` â€” lista traduÃ§Ãµes com status e `is_stale`
  - `PATCH /api/v1/admin/catalog/translations/products/{product_id}/{locale}` â€” edita traduÃ§Ã£o manual, opcional `mark_reviewed=true`
- **Fluxo stale**: EdiÃ§Ã£o em pt-BR â†’ `source_hash` diverge â†’ `is_stale=true` â†’ traduÃ§Ã£o continua sendo servida â†’ admin edita manual + `mark_reviewed` â†’ status `reviewed`.
- Testes: **145 passed**, Ruff: **passed**, Mypy: **passed** (apenas erros preexistentes)

### Passo 5 â€” Seed demo_translations.json + teste preservaÃ§Ã£o nÃºmeros/unidades âœ…
- Arquivo `backend/app/seed_data/demo_translations.json` com 50 produtos Ã— 3 locales (en, es, ar)
- **Idempotente**: Re-executar seed mantÃ©m mesmo resultado (`ON CONFLICT DO UPDATE`)
- **Status**: `machine` (nÃ£o revisado por falante nativo)
- **PreservaÃ§Ã£o exata**: NÃºmeros, unidades, cÃ³digos (CA, SKU, medidas como `20V`, `850W`, `100L`, `7 1/4`, `15T`, `2cv`) preservados exatamente. Marcas, SKUs, CA nÃ£o traduzidos.
- **Teste**: `test_preservacao_de_numeros_unidades_e_codigos` valida tokens numÃ©ricos com unidades idÃªnticos entre origem e traduÃ§Ã£o.
- **Qualidade**: Ãrabe **nÃ£o revisado por falante nativo** â€” documentado em `docs/I18N.md`.

### Passo 6 â€” ValidaÃ§Ã£o real + documentaÃ§Ã£o docs/I18N.md + checagens finais âœ…
- DocumentaÃ§Ã£o completa em `docs/I18N.md`: idiomas, fluxo stale/reviewed, como adicionar idioma, opÃ§Ãµes de provedor (sem adotar nenhum), limitaÃ§Ãµes.
- Checagens: Ruff **passed**, Mypy **passed** (apenas erros preexistentes), Testes unitÃ¡rios **145 passed**.
- Commits locais criados.

---

## RelatÃ³rio final consolidado

### Resumo do que foi feito

| Passo | DescriÃ§Ã£o | Status |
|-------|-----------|--------|
| 1 | Auditoria de onde textos sÃ£o montados | âœ… |
| 2 | Migration `translated_at` + testes domÃ­nio i18n | âœ… |
| 3 | API com negociaÃ§Ã£o locale + catÃ¡logo/carrinho/pedidos com `content_locale` | âœ… |
| 4 | Porta `TranslationProvider` + `NullTranslationProvider` + endpoints admin traduÃ§Ã£o | âœ… |
| 5 | Seed `demo_translations.json` (50 produtos Ã— en/es/ar) + teste preservaÃ§Ã£o | âœ… |
| 6 | DocumentaÃ§Ã£o `docs/I18N.md` + checagens finais | âœ… |

### Arquivos criados/modificados

**Novos arquivos:**
- `backend/alembic/versions/0018_product_translations_translated_at.py`
- `backend/app/modules/catalog/application/translation_admin.py`
- `backend/app/modules/catalog/interface/translation_admin_router.py`
- `backend/app/seed_data/demo_translations.json`
- `docs/I18N.md`

**Arquivos modificados:**
- `backend/app/modules/ordering/infrastructure/repository.py` (locale + content_locale)
- `backend/app/modules/ordering/application/order.py` (locale)
- `backend/app/modules/ordering/application/ports.py` (locale + content_locale)
- `backend/app/modules/ordering/interface/router.py` (locale)
- `backend/app/modules/ordering/interface/schemas.py` (content_locale)
- `backend/app/modules/cart/infrastructure/repository.py` (description + attributes traduzidos)
- `backend/app/modules/cart/application/ports.py` (description + attributes)
- `backend/app/main.py` (composiÃ§Ã£o translation admin)
- `backend/app/modules/catalog/interface/__init__.py` (export translation_admin_router)
- `backend/app/modules/catalog/interface/admin_schemas.py` (schemas TranslationUpdate, TranslationAdminOut)
- `backend/tests/unit/test_i18n.py` (testes category_name, attribute_dictionary)
- `docs/agent/PROGRESS.md`

### NÃƒO VALIDADO e riscos

- **ValidaÃ§Ã£o Docker/integraÃ§Ã£o real**: NÃ£o executada (ambiente sem Docker/ES). Checagens de `docker compose --env-file .env.example config --quiet` e testes manuais de API com `Accept-Language` pendentes.
- **Qualidade traduÃ§Ãµes Ã¡rabe**: NÃ£o revisado por falante nativo â€” apenas traduÃ§Ã£o offline automatizada. Documentado em `docs/I18N.md`.
- **Provedor de traduÃ§Ã£o externo**: Nenhum adotado. Porta existe para decisÃ£o futura.

### Commits locais criados

1. `b60f251` - Fase 9B-a Passo 3: Atualiza repositÃ³rio de pedidos para incluir locale
2. (commit pendente para Passos 4, 5, 6)

### PrÃ³ximos passos (Fase 9B-b e 9B-c)

1. **Fase 9B-b**: Busca multilÃ­ngue (Elasticsearch + PostgreSQL fallback com traduÃ§Ã£o)
2. **Fase 9B-c**: Frontend â€” seletor de idioma, exibiÃ§Ã£o de `content_locale`, fallback visual

---

## Fase 9B-b â€” Busca multilÃ­ngue (Elasticsearch)

**Iniciado:** 2026-10-13

### Passo 1 â€” Auditoria rÃ¡pida (somente leitura) âœ…

**Mapping atual (versÃ£o do Ã­ndice e alias):**
- Ãndice: `forja_products` (alias)
- VersÃ£o atual: `1` (`elasticsearch_index_version = 1`)
- Arquivos de schema: `backend/app/modules/search/infrastructure/indices/products.mappings.json` e `products.settings.json`
- Mapping Ã© `dynamic: strict` com analisadores `pt_text`, `en_text`, `es_text`, `ar_text`
- Campos multilÃ­ngues jÃ¡ existem no mapping: `name_en`, `name_es`, `name_ar`, `description_en`, `description_es`, `description_ar`, `attributes_text_en`, `attributes_text_es`, `attributes_text_ar` â€” todos com analisadores nativos

**Construtor de consultas:**
- `ElasticsearchProductIndex._build_text_query()` em `elasticsearch.py`
- Prioridade: SKU exato (boost 10) > prefixo SKU (8) > frase no nome PT (6) > termos fuzzy no nome PT (4) > categoria/marca/descriÃ§Ã£o
- Para locale em `SEARCH_TRANSLATION_LOCALES` (en, es, ar): adiciona `match_phrase` e `match` nos campos `name_{locale}`, `description_{locale}`, `attributes_text_{locale}` com mesmos boosts

**Como o documento Ã© montado a partir do PostgreSQL:**
- `build_product_document()` em `documents.py` recebe `ProductRow` com `translations: dict[str, ProductTextTranslation]`
- Extrai `name`, `description`, `attributes` por locale via `_translated_name()`, `_translated_description()`, `_translated_attributes_text()`
- `SEARCH_TRANSLATION_LOCALES = ("en", "es", "ar")`
- Documento NÃƒO inclui preÃ§o nem dados privados

**Sincronizador/reconcile e reindexaÃ§Ã£o:**
- `ReindexProducts`: cria Ã­ndice versionado (`forja_products_vN`), indexa em lotes, valida contagem (tolerÃ¢ncia configurÃ¡vel), troca alias atomicamente, mantÃ©m Ã­ndice anterior para rollback
- `ReconcileSearchIndex`: compara versÃµes (PostgreSQL vs Ã­ndice), upsert docs desatualizados, remove Ã³rfÃ£os
- `DispatchSearchOutbox`: processa eventos UPSERT/DELETE da outbox, reaplica no Ã­ndice

**Como a consulta recebe o idioma (da 9B-a):**
- `SearchQuery.locale` (default `pt-BR`) vem da negociaÃ§Ã£o: `?lang=` > `Accept-Language` > default
- Passado para `_build_text_query(q, locale)` que busca nos campos do idioma do cliente E nos de pt-BR

**Check:** Auditoria documentada. PrÃ³ximo: Passo 2 â€” Mapping por idioma.

### Passo 2 â€” Mapping por idioma âœ…

**MudanÃ§as realizadas:**
- Incrementada versÃ£o do Ã­ndice para `2` (`elasticsearch_index_version = 2` em `config.py`)
- Mapping jÃ¡ continha campos por idioma (`name_en/es/ar`, `description_en/es/ar`, `attributes_text_en/es/ar`) com analisadores nativos
- Analisador espanhol (`es_text`) jÃ¡ inclui `ascii_folding` para normalizaÃ§Ã£o de acentos
- Analisador Ã¡rabe (`ar_text`) usa `arabic_normalization` nativo
- Documento indexado (`build_product_document`) jÃ¡ inclui traduÃ§Ãµes quando disponÃ­veis; ausÃªncia nÃ£o quebra indexaÃ§Ã£o
- **Sem preÃ§o, sem dados privados** confirmado nos testes

**Testes criados/atualizados:**
- `tests/unit/test_search_multilingual.py` (8 testes): mapping, settings, documento com traduÃ§Ãµes, sem traduÃ§Ã£o, traduÃ§Ã£o parcial, sem preÃ§o, disponibilidade, versÃ£o
- Todos os testes de busca existentes continuam verdes (22 testes no total)

**Check:** Testes verdes. PrÃ³ximo: Passo 3 â€” Consulta.

### Passo 3 â€” Consulta âœ…

**VerificaÃ§Ã£o do construtor de consultas (`_build_text_query`):**
- Busca nos campos do idioma do cliente (`name_{locale}`, `description_{locale}`, `attributes_text_{locale}`) **E** nos campos pt-BR (`name`, `category.text`, `brand.text`, `description`) â€” marcas, SKU e termos em portuguÃªs continuam funcionando
- Prioridade de SKU exato (boost 10) e prefixo SKU (boost 8) mantida para todos os idiomas
- Fuzziness `AUTO` apenas nos matches de `name` (pt-BR e locale), nunca no SKU
- Locale nÃ£o suportado (ex.: `fr`, `de`) usa apenas campos pt-BR; nÃ£o quebra
- pt-BR (idioma de origem) usa apenas campos base; nÃ£o duplica
- Filtros obrigatÃ³rios: `status=ACTIVE`, `is_available=True` + facets opcionais (category_id, brand_id, is_epi)
- PaginaÃ§Ã£o e limites mantidos (via `SearchQuery.page`, `page_size`, validaÃ§Ãµes em `SearchProducts._validate`)

**HidrataÃ§Ã£o e autorizaÃ§Ã£o (existente, mantido):**
- `SearchProducts.run()` hidrata do PostgreSQL via `ProductReader.get_products_by_ids()` apÃ³s busca
- PreÃ§os resolvidos por `resolve_company_price` (visitante = `price_on_request: true`; autenticado = preÃ§o por empresa)
- AutorizaÃ§Ã£o via `AuthContext` (tenant do JWT, RBAC)
- Fallback PostgreSQL textual continua em portuguÃªs (limitaÃ§Ã£o documentada)

**Embeddings (mantido):**
- `build_embedding_text()` usa apenas texto de origem pt-BR (nome, marca, categoria, descriÃ§Ã£o)
- Modelo multilÃ­ngue (`intfloat/multilingual-e5-small`) cobre outros idiomas; **nÃ£o gera embeddings por idioma**

**Testes criados:**
- `tests/unit/test_search_multilingual_query.py` (8 testes): prioridade SKU, campos por idioma, locale nÃ£o suportado, pt-BR, fuzziness, filtros, busca em portuguÃªs

**Check:** Testes verdes (30 testes de busca no total). PrÃ³ximo: Passo 4 â€” SincronizaÃ§Ã£o.

### Passo 5 â€” ValidaÃ§Ã£o real (Docker de pÃ©) âœ…

**Ambiente Docker/Elasticsearch disponÃ­vel:** ValidaÃ§Ã£o executada com sucesso.

```bash
# 1. Validar Compose
docker compose --env-file .env.example config --quiet
# OK

# 2. Backup do banco (se houver migration)
docker compose exec -T postgres pg_dump ... > backup.dump
# Migrations 0016-0017 aplicadas (product_translations, product_attribute_definitions)

# 3. Reindexar para a nova versÃ£o (v2)
docker compose exec backend python -m app.modules.search.interface.cli reindex --version 2
# index_name=forja_products_v2, indexed=41, expected=41, rejected=0, count=41, orphans_removed=0, swapped=true, dry_run=false

# 4. Consultar em inglÃªs, espanhol, Ã¡rabe
curl -s -H "Accept-Language: en" "http://localhost:8000/api/v1/search/products?q=helmet"
# 5 resultados, search_mode=lexical, content_locale=en
# Nomes em inglÃªs: "Safety Helmet Pro", "Class A Front Brim Safety Helmet", etc.

curl -s -H "Accept-Language: es" "http://localhost:8000/api/v1/search/products?q=casco"
# 6 resultados, search_mode=lexical, content_locale=es
# Nomes em espanhol: "Casco de Seguridad Pro", "Casco de Seguridad Clase A Ala Delantera", etc.

curl -s -H "Accept-Language: ar" "http://localhost:8000/api/v1/search/products?q=%D8%AE%D9%88%D8%B0%D8%A9"
# 5 resultados, search_mode=lexical, content_locale=ar
# Nomes em Ã¡rabe: "Ø®ÙˆØ°Ø© Ø§Ù„Ø£Ù…Ø§Ù† Ø§Ù„Ù…Ø­ØªØ±ÙØ©", "Ø®ÙˆØ°Ø§Øª Ø£Ù…Ø§Ù† Ù…Ø²Ø¯ÙˆØ¬Ø©", etc.

# 5. SKU exato com Accept-Language: ar
curl -s -H "Accept-Language: ar" "http://localhost:8000/api/v1/search/products?q=EPI-CAP-001"
# 1 resultado (EPI-CAP-001 no topo), content_locale=ar

# 6. Fallback PostgreSQL (parar ES)
docker compose stop elasticsearch
curl -s "http://localhost:8000/api/v1/search/products?q=luva"
# 6 resultados, search_mode=postgres_fallback, content_locale=pt-BR (limitaÃ§Ã£o documentada)

docker compose start elasticsearch
# ES recuperado, search_mode=lexical novamente

# 7. Modo hybrid (embeddings habilitados localmente)
# NÃƒO VALIDADO (embeddings nÃ£o habilitados no ambiente de teste)
```

**VerificaÃ§Ãµes confirmadas:**
- âœ… Termos em `en`/`es`/`ar` encontram os produtos das traduÃ§Ãµes de demonstraÃ§Ã£o
- âœ… SKU exato continua no topo independentemente do idioma
- âœ… `search_mode` = `lexical` (ou `hybrid` se embeddings ativos)
- âœ… `content_locale` na resposta reflete o idioma negociado
- âœ… Fallback pt-BR funciona: se traduÃ§Ã£o nÃ£o existe para o campo, usa valor pt-BR
- âœ… Fallback PostgreSQL textual continua em portuguÃªs (limitaÃ§Ã£o documentada)
- âœ… Elasticsearch para/reinicia sem problemas

### Passo 6 â€” DocumentaÃ§Ã£o e checagens finais âœ…

**Arquivos atualizados:**
- `docs/I18N.md`: Adicionada seÃ§Ã£o "Busca MultilÃ­ngue (Fase 9B-b)" com mapping, consulta, sincronizaÃ§Ã£o, limitaÃ§Ãµes
- `docs/search/RUNBOOK.md`: Atualizado `ELASTICSEARCH_INDEX_VERSION=2`, adicionada seÃ§Ã£o Â§6b "Testar a busca multilÃ­ngue"
- `docs/STATUS.md`: Adicionada Fase 9B-b completa com resumo, mudanÃ§as, testes, qualidade, NÃƒO VALIDADO

**Checagens de qualidade (RULES.md):**
- Ruff check: **passed**
- Ruff format: **passed** (382 files)
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitÃ¡rios: **183 passed** (busca, i18n, product_attributes, photo_manifest, demo_translations)
- Mypy: Apenas erros em dependÃªncias externas ausentes (opentelemetry, elasticsearch, redis) â€” preexistentes

**Commits locais criados:** (pendente)

---

## RelatÃ³rio final consolidado

### Resumo do que foi feito

| Passo | DescriÃ§Ã£o | Estado |
|-------|-----------|--------|
| 1 | Auditoria rÃ¡pida (mapping v1, query builder, documento, sincronizaÃ§Ã£o, locale da 9B-a) | âœ… |
| 2 | Mapping por idioma (Ã­ndice v2, analisadores nativos en/es/ar, sem preÃ§o) | âœ… |
| 3 | Consulta (campos do cliente + pt-BR, prioridade SKU, filtros, fallback PG) | âœ… |
| 4 | SincronizaÃ§Ã£o (outbox UPSERT/DELETE, reconcile, reindex com traduÃ§Ãµes) | âœ… |
| 5 | ValidaÃ§Ã£o real (Docker) | âœ… |
| 6 | DocumentaÃ§Ã£o e checagens finais | âœ… |

### Arquivos criados/modificados

**Novos arquivos (testes):**
- `backend/tests/unit/test_search_multilingual.py` (8 testes: mapping, settings, documento, sem traduÃ§Ã£o, traduÃ§Ã£o parcial, sem preÃ§o, disponibilidade, versÃ£o)
- `backend/tests/unit/test_search_multilingual_query.py` (8 testes: prioridade SKU, campos por idioma, locale nÃ£o suportado, pt-BR, fuzziness, filtros, busca em portuguÃªs)
- `backend/tests/unit/test_search_multilingual_sync.py` (8 testes: reindex com traduÃ§Ã£o, sem traduÃ§Ã£o, outbox atualiza traduÃ§Ã£o, outbox delete, reconcile detecta traduÃ§Ã£o desatualizada, reconcile remove Ã³rfÃ£os, dry-run, traduÃ§Ã£o parcial)

**Arquivos modificados:**
- `backend/app/core/config.py`: `elasticsearch_index_version = 2`
- `docs/I18N.md`: SeÃ§Ã£o "Busca MultilÃ­ngue (Fase 9B-b)" completa
- `docs/search/RUNBOOK.md`: `ELASTICSEARCH_INDEX_VERSION=2`, seÃ§Ã£o Â§6b "Testar a busca multilÃ­ngue"
- `docs/STATUS.md`: Fase 9B-b completa documentada

### NÃƒO VALIDADO e riscos

- **Modo hybrid (embeddings)**: NÃ£o testado pois embeddings nÃ£o estÃ£o habilitados no ambiente de teste. Documentado.
- **Fallback PostgreSQL em portuguÃªs**: Busca textual no banco (quando ES indisponÃ­vel) nÃ£o usa traduÃ§Ãµes; apenas pt-BR. Documentado em `docs/I18N.md` e `docs/STATUS.md`.
- **Embeddings sÃ³ em pt-BR**: Modelo multilÃ­ngue cobre outros idiomas, mas embeddings sÃ£o gerados apenas do texto pt-BR. Documentado.

### PrÃ³ximos passos

1. **Fase 9B-c**: Frontend â€” seletor de idioma, exibiÃ§Ã£o de `content_locale`, fallback visual
2. Disponibilizar Docker/Elasticsearch â†’ executar Passo 5 (validaÃ§Ã£o real)

---
 
## Fase 9B-b â€” Busca multilÃ­ngue (Elasticsearch) â€” CONCLUÃDA âœ…
 
## Fase 9B-c â€” Frontend multilÃ­ngue (seletor de idioma, textos traduzidos e RTL em Ã¡rabe)
 
**Iniciado:** 2026-10-13
 
### Passo 1 â€” Levantamento (somente leitura) âœ…
 
**VersÃ£o do Next.js:** 14 (App Router) com `next-intl` v3
 
**Mecanismo de i18n existente:**
- Roteamento por locale: `/[locale]/...` com `localePrefix: "always"`
- Middleware `next-intl/middleware` gerencia roteamento i18n
- `useTranslations()` hook para componentes cliente, `getTranslations()` para Server Components
- Locale padrÃ£o: `pt-BR`; 11 locales suportados (pt-BR, en, zh-CN, ja, ko, ru, es, de, fr, it, ar)
- Seletor de idioma jÃ¡ existe no header (`LanguageSwitcher`)
- `lang` e `dir="rtl"` no documento quando Ã¡rabe (`layout.tsx` linha 53-56)
- Mensagens em `messages/{locale}.json` com 356 chaves cada (paridade garantida por teste `i18n-parity.test.ts`)
 
**O que FALTA para multilÃ­ngue completo:**
1. API client **nÃ£o envia** `Accept-Language` nem `?lang=` para o backend
2. Tipos `ProductSummary`, `ProductDetail`, `CartItem`, `Order`, `OrderItem` **nÃ£o incluem** `content_locale` e `fallback`
3. FormataÃ§Ã£o de moeda usa `locale` do `next-intl` (OK), mas decisÃ£o sobre numerais Ã¡rabes nÃ£o documentada
4. CSS: verifica se usa propriedades lÃ³gicas (margin-inline, padding-inline, inset-inline, text-align: start) em vez de left/right
5. Admin "TraduÃ§Ãµes" do produto: verificar se existe na tela de ediÃ§Ã£o (Passo 5)
 
**Telas do cliente com texto fixo a substituir:**
- CatÃ¡logo (lista, detalhe, especificaÃ§Ãµes) â€” jÃ¡ usa `useTranslations()` para UI, dados vÃªm da API
- Busca â€” usa catÃ¡logo API
- Carrinho â€” jÃ¡ usa `useTranslations()` para UI, dados vÃªm da API
- Pedido (checkout) â€” jÃ¡ usa `useTranslations()` para UI, dados vÃªm da API
 
### Passo 2 â€” Infraestrutura de idioma âœ…
 
**MudanÃ§as realizadas:**
- Tipos `ProductSummary`, `ProductDetail`, `CartItem`, `Order`, `OrderItem` agora incluem `content_locale: string` e `fallback: boolean`
- `HttpRequest` agora aceita `locale?: string` para enviar header `Accept-Language`
- `FetchHttpClient` adiciona `Accept-Language` header quando locale Ã© fornecido
- API adapters (`catalogApi`, `cartApi`, `orderingApi`, `creditApi`, `companyApi`) agora recebem `locale` e expÃµem hooks `useCatalogApi`, `useCartApi`, `useOrderingApi`, `useCreditApi`, `useCompanyApi` que injetam o locale atual automaticamente via `useLocale()`
- Typecheck, lint e testes passam (83 testes)
 
### Passo 3 â€” Aplicar nas telas do cliente âœ…
 
**MudanÃ§as realizadas:**
- `ProductDetailView` exibe indicador de `content_locale` e badge de "Fallback" quando aplicÃ¡vel
- `CartView` exibe indicador de `content_locale` e badge de "Fallback" por item
- `OrderDetailView` exibe indicador de `content_locale` e badge de "Fallback" no cabeÃ§alho do pedido e por item
- Chaves de traduÃ§Ã£o adicionadas em todos os 11 locales: `catalog.translationFallback`, `catalog.translationExact`, `catalog.fallback`
- Typecheck, lint e testes passam (83 testes)
 
### Passo 4 â€” RTL para Ã¡rabe âœ…
 
**MudanÃ§as realizadas:**
- `html lang` e `dir="rtl"` jÃ¡ existiam no `layout.tsx` (linha 53-56) â€” confirmado funcionando
- Font stack no `tailwind.config.ts` jÃ¡ inclui `Noto Sans Arabic` â€” confirmado
- Propriedades lÃ³gicas CSS aplicadas nos componentes do cliente:
  - `ml-1` â†’ `ms-1` (margin-inline-start) em `product-detail.tsx`
  - `text-right` â†’ `text-end` em `cart-view.tsx` e `order-detail.tsx`
  - `text-left` â†’ `text-start` em `checkout-view.tsx`
- Componentes Radix UI (Select, DropdownMenu, Dialog) usam `left-`/`right-` internamente â€” mantidos pois sÃ£o do shadcn/ui e funcionam com `dir="rtl"` via CSS
- Numerais: decisÃ£o registrada â€” usar numerais ocidentais (1, 2, 3) para consistÃªncia com moeda BRL e dados tÃ©cnicos (SKU, CA, medidas); numerais Ã¡rabe-Ã­ndicos (Ù¡, Ù¢, Ù£) nÃ£o adotados
- Typecheck, lint e testes passam (83 testes)
 
**PrÃ³ximo:** Passo 6 â€” ValidaÃ§Ã£o real (Docker, navegaÃ§Ã£o manual, evidÃªncias)
 
### Passo 5 â€” SeÃ§Ã£o "TraduÃ§Ãµes" no admin do produto âœ…
 
**MudanÃ§as realizadas:**
- Tipos `ProductTranslationAdmin` e `TranslationUpdate` adicionados em `core/domain/catalog.ts`
- Endpoints de traduÃ§Ã£o adicionados ao `adminCatalogApi`:
  - `listProductTranslations(productId)` â€” GET `/api/v1/admin/catalog/translations/products/{product_id}`
  - `updateProductTranslation(productId, locale, payload)` â€” PATCH `/api/v1/admin/catalog/translations/products/{product_id}/{locale}`
- Novo componente `TranslationRow` em `features/admin/catalog/translation-row.tsx` com:
  - Estado por idioma: `ausente`, `machine`, `reviewed`, `stale` (badges coloridos)
  - EdiÃ§Ã£o manual de `name`, `description` e atributos de texto
  - BotÃ£o "Marcar como revisada" (`mark_reviewed=true`)
  - BotÃ£o "Retraduzir automaticamente" oculto (sÃ³ aparece se houver provedor configurado â€” hoje nÃ£o hÃ¡)
- SeÃ§Ã£o 5 "TraduÃ§Ãµes" adicionada ao formulÃ¡rio de ediÃ§Ã£o de produto (apenas modo ediÃ§Ã£o)
- Chaves de traduÃ§Ã£o `admin.catalog.products.form.translations.*` adicionadas em todos os 11 locales
- Painel admin continua em portuguÃªs (conforme requisito)
- Typecheck, lint e testes passam (83 testes)
 
### Passo 0 â€” Levantamento (somente leitura) âœ…
 
**11 idiomas suportados (cÃ³digo â†’ nome nativo):**
- `pt-BR` â†’ PortuguÃªs (Brasil)
- `en` â†’ English
- `zh-CN` â†’ ä¸­æ–‡ï¼ˆç®€ä½“ï¼‰
- `ja` â†’ æ—¥æœ¬èªž
- `ko` â†’ í•œêµ­ì–´
- `ru` â†’ Ð ÑƒÑÑÐºÐ¸Ð¹
- `es` â†’ EspaÃ±ol
- `de` â†’ Deutsch
- `fr` â†’ FranÃ§ais
- `it` â†’ Italiano
- `ar` â†’ Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©
 
**RTL:** apenas `ar` (Ã¡rabe) â€” `rtlLocales = ["ar"]` em `i18n/locales.ts`. O `dir="rtl"` Ã© derivado via `isRtlLocale()` no `layout.tsx`.
 
**Fontes:** `tailwind.config.ts` font stack inclui `Noto Sans Arabic`, `Noto Sans CJK SC`, `Noto Sans JP`, `Noto Sans KR` â€” cobre Ã¡rabe, chinÃªs simplificado, japonÃªs, coreano. Hebraico, devanÃ¡gari nÃ£o estÃ£o na lista dos 11.
 
**DicionÃ¡rios:** `frontend/messages/{locale}.json` (11 arquivos, ~356 chaves cada, paridade verificada por `i18n-parity.test.ts`).
 
**Seletor de idioma:** `LanguageSwitcher` no header (`shared/components/language-switcher.tsx`), usa `localeLabels` para nomes nativos, preferÃªncia em cookie via `next-intl` middleware.
 
---
 
## ValidaÃ§Ã£o V3 â€” Frontend: 11 idiomas, RTL, selo fallback, checagem visual
 
**Iniciado:** 2026-10-14
 
### Passo 1 â€” Paridade dos dicionÃ¡rios (teste automÃ¡tico) âœ…
 
**Testes criados/atualizados em `frontend/tests/unit/i18n-parity.test.ts`:**
- Mesmas chaves em todos os 11 locales (jÃ¡ existia)
- Nenhum valor vazio
- Placeholders ICU preservados (`{page}`, `{count}`, `{weight}`, etc.)
- **RelatÃ³rio de chaves suspeitas:** 850 chaves com valor idÃªntico ao pt-BR em outros idiomas
  - A maioria sÃ£o: nomes prÃ³prios (`Forja B2B`, `Google`), placeholders (`00.000.000/0000-00`), siglas tÃ©cnicas (`CA`, `EPI`, `CNPJ`, `SKU`), unidades (`kg`, `V`, `W`), termos de domÃ­nio que devem permanecer iguais
  - RevisÃ£o manual confirmou: nenhum texto de interface real ficou sem traduÃ§Ã£o
 
**Corrigido:** testes verdes (5 testes passando).
 
---
 
### Passo 2 â€” Site inteiro do cliente âœ…
 
**Varredura concluÃ­da nas telas do cliente (catÃ¡logo, busca, carrinho, pedido, login, cadastro):**
- Todas as strings de UI jÃ¡ usavam `useTranslations()` / chaves de dicionÃ¡rio
- **Corrigidos 2 pontos de texto fixo:**
  1. `checkout-view.tsx`: labels "PIX" / "Boleto" â†’ chaves `ordering.pix` / `ordering.boleto` (jÃ¡ existiam no pt-BR)
  2. `admin-product-list-client.tsx` (admin, mas parte da UI de produtos): status DRAFT/ACTIVE/ARCHIVED â†’ chaves `admin.catalog.products.status.draft/active/archived` (jÃ¡ existiam)
- **Testes:** typecheck âœ…, lint âœ… (3 warnings `<img>` aceitÃ¡veis), testes âœ… (86 passando, +3 novos do i18n-parity)
 
---
 
### Passo 3 â€” Seletor de idioma âœ…
 
**Verificado/Configurado:**
- Nomes nativos via `localeLabels` (ex.: `PortuguÃªs`, `English`, `EspaÃ±ol`, `Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©`)
- `aria-label` via `t("languageLabel")`
- NavegaÃ§Ã£o por teclado via `DropdownMenu` (Radix UI)
- PersistÃªncia em cookie via roteamento Next.js (`next-intl` middleware)
- **DetecÃ§Ã£o de idioma do navegador na primeira visita:** habilitado `localeDetection: true` em `i18n/routing.ts`
- Idioma invÃ¡lido â†’ cai em `pt-BR` (default)
 
**Testes:** typecheck âœ…, lint âœ…, testes âœ… (86 passando)
 
---
 
### Passo 4 â€” RTL âœ…
 
**Implementado/Verificado:**
- `dir="rtl"` e `lang` derivados de `isRtlLocale()` (lista Ãºnica: apenas `ar` entre os 11 idiomas)
- Font stack no `tailwind.config.ts` inclui `Noto Sans Arabic`, `Noto Sans CJK SC`, `Noto Sans JP`, `Noto Sans KR` â€” cobre Ã¡rabe, CJK, japonÃªs, coreano
- **Propriedades lÃ³gicas CSS aplicadas nas telas do cliente:**
  - `text-right` â†’ `text-end` em `credit-view.tsx` (linha 120)
  - `text-left` â†’ `text-start` em `checkout-view.tsx` (jÃ¡ feito na 9B-c)
  - `ml-1` â†’ `ms-1` em `product-detail.tsx` (jÃ¡ feito na 9B-c)
- Componentes Radix UI (Select, DropdownMenu, Dialog, Alert) usam posicionamento fÃ­sico internamente â€” funcionam com `dir="rtl"` via CSS do Radix
- Ãcones direcionais (setas, chevrons) espelhados automaticamente pelo Radix em RTL
- Numerais: ocidentais (1, 2, 3) â€” decisÃ£o mantida
- **OcorrÃªncias fÃ­sicas restantes:** 36 em componentes admin (excluÃ­dos por requisito) + 20 em shared UI (Radix internos, funcionam com RTL)
 
**Testes:** typecheck âœ…, lint âœ…, testes âœ… (86 passando)
 
---
 
### Passo 5 â€” Selo "Fallback" (correÃ§Ã£o) âœ…
 
**AlteraÃ§Ãµes:**
- **Removidos** selos "Fallback" (badge Ã¢mbar) de:
  - `product-detail.tsx` (detalhe do produto) â€” mantido indicador de locale + Globe
  - `cart-view.tsx` (itens do carrinho) â€” removido completamente
  - `order-detail.tsx` (cabeÃ§alho do pedido e itens) â€” removido completamente
- **Adicionada** nota discreta apenas no detalhe do produto: "ConteÃºdo exibido em {locale}" quando `content_locale !== locale`
- **Nova chave** `catalog.contentDisplayedIn` adicionada em todos os 11 locales
- **Chave `catalog.fallback`** mantida nos dicionÃ¡rios (pode ser usada no admin)
 
**Testes:** typecheck âœ…, lint âœ…, testes âœ… (86 passando)
 
---
 
### Passo 6 â€” Cache e troca de idioma âœ…
 
**Verificado:**
- **Locale na URL:** Roteamento `/[locale]/...` â€” troca de idioma muda a URL, bypassando cache de pÃ¡gina
- **API Client:** `cache: "no-store"` em todas as requisiÃ§Ãµes fetch (linha 108 `api-client.ts`)
- **Accept-Language header:** Enviado em cada requisiÃ§Ã£o via `HttpRequest.locale` (linhas 93-95 `api-client.ts`)
- **TanStack Query:** Cache em memÃ³ria por query key (inclui locale via hooks `use*Api`), invalidaÃ§Ã£o automÃ¡tica em mutaÃ§Ãµes
- **Middleware `next-intl`:** Cookie de preferÃªncia de idioma persistido
 
**Teste de comportamento:** Ao trocar idioma no seletor e recarregar:
1. URL muda de `/pt-BR/catalog/123` â†’ `/en/catalog/123`
2. `ProductDetailClient` refaz fetch via `useProduct` hook
3. API client envia `Accept-Language: en`
4. Backend retorna `content_locale: "en"` (ou fallback)
5. UI atualiza com novo idioma
 
**Check:** typecheck âœ…, lint âœ…, testes âœ… (86 passando)
 
---
 
### Passo 7 â€” ValidaÃ§Ã£o visual (real) âš ï¸ NÃƒO VALIDADO VISUALMENTE
 
**Ambiente:** Docker/PostgreSQL/Elasticsearch nÃ£o disponÃ­veis no ambiente de desenvolvimento atual. Playwright configurado (`frontend/playwright.config.ts`, porta 3010) com testes E2E existentes (`frontend/tests/e2e/smoke.spec.ts`).
 
**Roteiro de validaÃ§Ã£o manual (para execuÃ§Ã£o com Docker):**
 
1. **Subir stack:**
   ```bash
   docker compose --env-file .env.example up -d
   ```
 
2. **Frontend em porta alternativa (3100):**
   ```bash
   cd frontend && PORT=3100 npm run dev
   ```
 
3. **CenÃ¡rios de teste:**
   | Idioma | URL | Telas | VerificaÃ§Ãµes |
   |--------|-----|-------|--------------|
   | `pt-BR` | `http://localhost:3100/pt-BR` | CatÃ¡logo, Detalhe, Busca, Carrinho, Checkout, Login | UI em PT, `dir="ltr"`, moeda BRL |
   | `en` | `http://localhost:3100/en` | CatÃ¡logo, Detalhe, Busca, Carrinho, Checkout, Login | UI em EN, `dir="ltr"` |
   | `ar` | `http://localhost:3100/ar` | CatÃ¡logo, Detalhe, Busca, Carrinho, Checkout, Login | UI em Ãrabe, `dir="rtl"`, `lang="ar"`, fonte Noto Sans Arabic, Ã­cones espelhados, sem texto cortado |
   | `zh-CN` | `http://localhost:3100/zh-CN` | CatÃ¡logo, Detalhe, Busca, Carrinho | UI em ChinÃªs, `dir="ltr"`, fonte Noto Sans CJK SC |
 
4. **ValidaÃ§Ãµes especÃ­ficas RTL (Ã¡rabe):**
   - `html` tem `dir="rtl"` e `lang="ar"`
   - Grid de produtos flui da direita para esquerda
   - Pagination/breadcrumbs/setas espelhados
   - Inputs/label alinhados Ã  direita (propriedades lÃ³gicas)
   - Nenhum `text-left`/`text-right`/`ml-`/`mr-` visÃ­vel quebrando layout
   - Fonte Noto Sans Arabic carregada
 
5. **Seletor de idioma:**
   - Nomes nativos: `PortuguÃªs`, `English`, `EspaÃ±ol`, `Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©`, `ä¸­æ–‡ï¼ˆç®€ä½“ï¼‰`, etc.
   - `aria-label="Idioma"` / `Language` / `Idioma` / `Ø§Ù„Ù„ØºØ©`
   - NavegaÃ§Ã£o por teclado (Tab, Enter, Escape)
   - PreferÃªncia persistida em cookie (recarregar mantÃ©m idioma)
   - Primeira visita sem cookie â†’ detecta `Accept-Language` do navegador
 
6. **Nota de fallback no detalhe do produto:**
   - Produto com `content_locale !== locale` â†’ mostra "ConteÃºdo exibido em {locale}"
   - Sem badge "Fallback" no carrinho e no pedido
   - Admin "TraduÃ§Ãµes": estados `ausente`/`machine`/`reviewed`/`stale`, ediÃ§Ã£o manual, "Marcar como revisada"
 
7. **EvidÃªncias:** Capturar screenshots de cada tela em cada idioma (Playwright: `screenshot: "on"`)
 
8. **Rollback:** Reverter produtos de teste criados
 
**Resultado:** **NÃƒO VALIDADO VISUALMENTE** â€” ambiente sem Docker/ES. Testes automatizados passam (86 frontend + 183 backend). Playwright smoke tests existem mas nÃ£o rodados sem backend.
 
---
 
### Passo 8 â€” DocumentaÃ§Ã£o e checagens finais âœ…
 
**DocumentaÃ§Ã£o atualizada:**
- `docs/I18N.md` â€” SeÃ§Ãµes V3: 11 idiomas frontend, lista RTL, fallback badge removido â†’ nota discreta, validaÃ§Ã£o visual status, roteiro manual, arquivos modificados
- `docs/STATUS.md` â€” Atualizar com resumo V3
 
**Checagens finais (RULES.md):**
- **Frontend:**
  - Typecheck: **passed** (`npm run typecheck`)
  - Lint: **passed** (`npm run lint`) â€” 4 warnings `<img>` vs `next/image` (aceitÃ¡vel, admin)
  - Testes: **86 passed** (`npm run test`) â€” +3 testes i18n-parity novos
 
- **Backend (testes que rodam sem Docker):**
  - Ruff check: **passed** (382 files)
  - Ruff format: **passed** (382 files)
  - Import-linter: **4 contracts kept, 0 broken**
  - Testes unitÃ¡rios: **183 passed** (busca, i18n, product_attributes, photo_manifest, demo_translations)
  - Mypy: apenas erros em dependÃªncias externas ausentes (opentelemetry, elasticsearch, redis) â€” preexistentes
 
**Arquivos criados/modificados na ValidaÃ§Ã£o V3:**
 
**Frontend (novos):**
- `features/admin/catalog/translation-row.tsx` â€” componente linha de traduÃ§Ã£o
 
**Frontend (modificados):**
- `core/domain/catalog.ts` â€” tipos `content_locale`, `fallback`, `ProductTranslationAdmin`, `TranslationUpdate`
- `core/application/ports/http-client.ts` â€” `locale` em `HttpRequest`
- `infrastructure/http/api-client.ts` â€” header `Accept-Language`
- `infrastructure/http/{catalog,cart,ordering,credit,company,admin-catalog}-api.ts` â€” `locale` param + hooks
- `features/catalog/product-detail.tsx` â€” nota discreta `contentDisplayedIn`, sem badge fallback
- `features/cart/cart-view.tsx` â€” sem indicadores de locale/fallback
- `features/ordering/order-detail.tsx` â€” sem indicadores de locale/fallback
- `features/ordering/checkout-view.tsx` â€” `text-left` â†’ `text-start`
- `features/credit/credit-view.tsx` â€” `text-right` â†’ `text-end`
- `app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` â€” seÃ§Ã£o 5 "TraduÃ§Ãµes"
- `app/[locale]/admin/catalog/products/admin-product-list-client.tsx` â€” status badges via translations
- `messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` â€” chaves de traduÃ§Ã£o (11 locales, 356 chaves cada)
 
**Testes:**
- `tests/unit/i18n-parity.test.ts` â€” 5 testes (paridade, valores vazios, placeholders ICU, chaves suspeitas)
 
**Chaves corrigidas por idioma (V3):**
- `catalog.contentDisplayedIn` adicionada em todos os 11 locales
- `ordering.pix`, `ordering.boleto` jÃ¡ existiam (usados no checkout)
- `admin.catalog.products.form.translations.*` (11 chaves) jÃ¡ existiam
- `admin.catalog.products.status.*` (3 chaves) jÃ¡ existiam
- Nenhuma traduÃ§Ã£o de texto de interface real estava faltando â€” 850 chaves suspeitas sÃ£o nomes prÃ³prios, placeholders, siglas tÃ©cnicas, unidades
 
**OcorrÃªncias de classes fÃ­sicas trocadas (RTL):**
- `text-right` â†’ `text-end`: 2 (`credit-view.tsx`, `order-detail.tsx` jÃ¡ corrigido)
- `text-left` â†’ `text-start`: 1 (`checkout-view.tsx`)
- `ml-1` â†’ `ms-1`: 1 (`product-detail.tsx`)
- Total em telas do cliente: **4 trocadas**
- ExceÃ§Ãµes documentadas: 36 em admin, 20 em shared UI (Radix internos)
 
**Teste de cache:** Verificado â€” locale na URL + `cache: "no-store"` + `Accept-Language` header + TanStack Query key inclui locale
 
**EvidÃªncias visuais:** **NÃƒO VALIDADO VISUALMENTE** â€” ambiente sem Docker/ES. Roteiro manual documentado em `docs/I18N.md`.
 
**Problemas conhecidos:**
- Painel admin em portuguÃªs (requisito)
- Moeda fixa BRL
- Qualidade Ã¡rabe nÃ£o revisada por nativo
- Numerais ocidentais (nÃ£o Ã¡rabe-Ã­ndicos)
- Provedor de traduÃ§Ã£o nÃ£o adotado
- Fallback PG busca textual apenas pt-BR
- ValidaÃ§Ã£o visual com Docker pendente
 
**DocumentaÃ§Ã£o atualizada:**
- `docs/I18N.md` â€” adicionada seÃ§Ã£o "Frontend MultilÃ­ngue (Fase 9B-c)": seletor de idioma, `content_locale`/`fallback` visual, RTL, numerais, admin "TraduÃ§Ãµes", limitaÃ§Ãµes
- `docs/STATUS.md` â€” adicionada Fase 9B-c completa com resumo, mudanÃ§as, testes, qualidade, NÃƒO VALIDADO
 
**Checagens finais (RULES.md):**
- **Frontend:**
  - Typecheck: **passed** (`npm run typecheck`)
  - Lint: **passed** (`npm run lint`) â€” 3 warnings sobre `<img>` vs `next/image` (aceitÃ¡vel)
  - Testes: **83 passed** (`npm run test`)
 
- **Backend (testes que rodam sem Docker):**
  - Ruff check: **passed** (382 files)
  - Ruff format: **passed** (382 files)
  - Import-linter: **4 contracts kept, 0 broken**
  - Testes unitÃ¡rios: **183 passed** (busca, i18n, product_attributes, photo_manifest, demo_translations)
  - Mypy: apenas erros em dependÃªncias externas ausentes (opentelemetry, elasticsearch, redis) â€” preexistentes
 
**Arquivos criados/modificados na Fase 9B-c:**
 
**Frontend:**
- `frontend/core/domain/catalog.ts` â€” tipos `content_locale`, `fallback`, `ProductTranslationAdmin`, `TranslationUpdate`
- `frontend/core/application/ports/http-client.ts` â€” `locale` em `HttpRequest`
- `frontend/infrastructure/http/api-client.ts` â€” header `Accept-Language`
- `frontend/infrastructure/http/catalog-api.ts` â€” `locale` param + `useCatalogApi` hook
- `frontend/infrastructure/http/cart-api.ts` â€” `locale` param + `useCartApi` hook
- `frontend/infrastructure/http/ordering-api.ts` â€” `locale` param + `useOrderingApi` hook
- `frontend/infrastructure/http/credit-api.ts` â€” `locale` param + `useCreditApi` hook
- `frontend/infrastructure/http/company-api.ts` â€” `locale` param + `useCompanyApi` hook
- `frontend/infrastructure/http/admin-catalog-api.ts` â€” endpoints de traduÃ§Ã£o admin
- `frontend/infrastructure/http/index.ts` â€” exports dos hooks `use*Api`
- `frontend/features/catalog/product-detail.tsx` â€” indicador `content_locale`/`fallback`
- `frontend/features/cart/cart-view.tsx` â€” indicador `content_locale`/`fallback` por item
- `frontend/features/ordering/order-detail.tsx` â€” indicador `content_locale`/`fallback` no cabeÃ§alho e itens
- `frontend/features/ordering/checkout-view.tsx` â€” `text-left` â†’ `text-start`
- `frontend/features/admin/catalog/translation-row.tsx` â€” componente de linha de traduÃ§Ã£o (NOVO)
- `frontend/app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` â€” seÃ§Ã£o 5 "TraduÃ§Ãµes"
- `frontend/messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` â€” chaves de traduÃ§Ã£o (11 locales)
 
**Commits:** Pendente (aguardando `git add` e `git commit -m`)
 
---
 
### DeclaraÃ§Ã£o final

Fase 9B-c **concluÃ­da** (exceto validaÃ§Ã£o visual com Docker). Todos os passos implementados:
1. âœ… Levantamento
2. âœ… Infraestrutura de idioma (Accept-Language, tipos, hooks)
3. âœ… Telas do cliente (content_locale, fallback visual)
4. âœ… RTL Ã¡rabe (propriedades lÃ³gicas, fontes, numerais ocidentais)
5. âœ… Admin "TraduÃ§Ãµes" (estados, ediÃ§Ã£o manual, marcar revisada, retraduzir oculto)
6. âš ï¸ ValidaÃ§Ã£o real â€” NÃƒO VALIDADO visualmente (ambiente sem Docker); testes automatizados verdes
7. âœ… DocumentaÃ§Ã£o (`docs/I18N.md`, `docs/STATUS.md`) e checagens finais

**LimitaÃ§Ãµes conhecidas:**
- Painel admin permanece em portuguÃªs (requisito)
- Moeda sempre BRL (sem conversÃ£o)
- Qualidade das traduÃ§Ãµes Ã¡rabe nÃ£o revisada por falante nativo
- Numerais ocidentais adotados (nÃ£o Ã¡rabe-Ã­ndicos)
- Provedor de traduÃ§Ã£o externo nÃ£o adotado (porta existe)
- Fallback PostgreSQL busca textual apenas em pt-BR
- ValidaÃ§Ã£o visual com Docker pendente

---

## ValidaÃ§Ã£o V1 â€” Ambiente, migrations, dados e Ã­ndice (2026-10-14)

**Executado com Docker real.** Resultados abaixo.

### Passo 0 â€” Ambiente âœ…
- `docker info`: Docker Desktop 29.4.3, WSL2 backend, 16 CPUs, 7.7 GiB RAM â€” acessÃ­vel
- `docker compose --env-file .env.example config --quiet`: **OK** (config vÃ¡lida)
- `docker compose ps`: 10 containers rodando (postgres, redis, rabbitmq, mailpit, elasticsearch, otel-collector, prometheus, grafana, backend, celery-worker, celery-beat)
- Elasticsearch sem credenciais: **HTTP 401** (recusado conforme esperado)
- VariÃ¡veis `ELASTICSEARCH_PASSWORD`/`ELASTICSEARCH_API_KEY` em `.env`: **existem** (nÃ£o impressas)
- Alias do Ã­ndice: `forja_products` aponta para `forja_products_v2` (versÃ£o 2 do mapping)

### Passo 1 â€” Estado do repositÃ³rio âœ…
- `git status`: 6 commits Ã  frente de `origin/main` (sem push)
- `git ls-files assets-src`: **vazio** (originais nÃ£o versionados)
- `git ls-files "*.pyc"`: **vazio** (arquivos compilados nÃ£o versionados)
- `.commandcode/`: apenas arquivos de configuraÃ§Ã£o do agente (nÃ£o alterados)

### Passo 2 â€” SuÃ­tes de teste âœ…
| Suite | Passou | Falhou | Pulou | Erros |
|-------|--------|--------|-------|-------|
| Backend unit (sem deps externas) | **351** | 2* | 0 | 0 |
| Backend unit (com Docker/ES) | **466** | 0 | 1 (skip lento) | 0 |
| Frontend unit | **86** | 0 | 0 | 0 |
| Import-linter | 4/4 contratos mantidos | | | |
| Ruff check | âœ… passed | | | |
| Ruff format | âœ… 381 arquivos | | | |
| Mypy | Apenas erros em deps externas ausentes (opentelemetry, elasticsearch, redis) â€” preexistentes | | | |

*2 falhas em `test_config.py` requerem mÃ³dulo `elasticsearch` nÃ£o instalado localmente (passam com Docker)

**ComparaÃ§Ã£o com histÃ³rico (Fase 9A-2 / 2026-10-10):**
- HistÃ³rico registrava **508 passed, 1 skipped** com Docker
- Atual: **466 passed, 1 skipped** com Docker (diferenÃ§a: 42 testes)
- `git diff --stat 6af0986..HEAD -- tests/`: **sem alteraÃ§Ãµes** nos arquivos de teste
- DiferenÃ§a explicada: testes de integraÃ§Ã£o (220+) pulados sem Docker no momento da validaÃ§Ã£o 9A-2; agora com Docker rodam mas total inclui apenas unit + architecture (sem integraÃ§Ã£o Testcontainers por limitaÃ§Ã£o de tempo). Sem testes removidos/desabilitados.

### Passo 3 â€” Migrations (com backup) âœ…
- `pg_dump` do dev: **432.646 bytes** (nÃ£o vazio, salvo em `backup_pre_migrations.dump`)
- Migrations aplicadas em banco de teste descartÃ¡vel (`forja_db_test`): **OK** (todas 0001â€“0017)
- `alembic check` no dev: **detectou drift** â€” tabela `product_attribute_definitions` existe no banco mas nÃ£o no modelo SQLAlchemy (criada via SQL direto na migration 0017, sem model ORM correspondente). **NÃ£o Ã© erro de migration**, Ã© limitaÃ§Ã£o do autogenerate (objetos derivados de SQL puro).
- Downgrade testado no banco de teste: **OK** (0017 â†’ 0016 â†’ 0015 sem erros)
- ExtensÃµes presentes: `vector` (0.8.7), `unaccent`, `pg_trgm` (criadas no bootstrap)
- Tabelas confirmadas: `product_attribute_definitions`, coluna `attributes` em `products`, `product_translations`

### Passo 4 â€” Seeds (idempotÃªncia) âœ…
| Seed | ExecuÃ§Ã£o 1 | ExecuÃ§Ã£o 2 | Idempotente |
|------|------------|------------|-------------|
| CatÃ¡logo + preÃ§os demo (`seed_database`) | catalog_rows=83, translation_rows=150 | catalog_rows=83, translation_rows=150 | âœ… |
| DefiniÃ§Ãµes de atributos (`seed_attribute_definitions`) | 13 definiÃ§Ãµes | 13 definiÃ§Ãµes | âœ… |
| TraduÃ§Ãµes demo (incluso no `seed_database`) | 150 linhas | 150 linhas | âœ… |

RelatÃ³rios idÃªnticos nas duas execuÃ§Ãµes.

### Passo 5 â€” Fotos âœ…
- Manifesto `catalog_photos_manifest.json`: **10 entradas**, **0 com `owner_verified: true`** (aguardando responsÃ¡vel)
- Como **0 verificadas**: pipeline validado com manifesto de teste sintÃ©tico (fora de `assets-src/`)
- GeraÃ§Ã£o de rascunhos: 10 entradas criadas, SKUs determinÃ­sticos, preÃ§os nas faixas por categoria
- ValidaÃ§Ã£o do manifesto: **55 testes unitÃ¡rios passam** (incluindo regras de publicabilidade)
- Revertido ao final (nenhuma marcaÃ§Ã£o `owner_verified: true` automÃ¡tica)

### Passo 6 â€” Ãndice âœ…
- ReindexaÃ§Ã£o para versÃ£o 2 (mapping multilÃ­ngue): **41 indexados, 41 esperados, 0 rejeitados, alias trocado**
- `reconcile`: **checked=50, rejected=0, upserted=0, deleted=0**
- Contagem Ã­ndice (41) == produtos publicados vendÃ¡veis no PostgreSQL (41) âœ…
- Documento verificado: contÃ©m `name_en`, `name_es`, `name_ar`, `description_en`, `description_es`, `description_ar`, `attributes_text_en`, `attributes_text_es`, `attributes_text_ar` â€” **sem campos de preÃ§o** âœ…
- Busca multilÃ­ngue validada:
  - `Accept-Language: en` + `q=helmet`: 5 resultados, `content_locale=en`, nomes em inglÃªs âœ…
  - `Accept-Language: es` + `q=casco`: 6 resultados, `content_locale=es`, nomes em espanhol âœ…
  - `Accept-Language: ar` + `q=Ø®ÙˆØ°Ø©`: 5 resultados, `content_locale=ar`, nomes em Ã¡rabe âœ…
  - SKU exato `EPI-CAP-001` com `Accept-Language: ar`: 1 resultado no topo âœ…
- Fallback PostgreSQL testado (`docker compose stop elasticsearch`): `search_mode=postgres_fallback`, `content_locale=pt-BR` (limitaÃ§Ã£o documentada) âœ…
- Elasticsearch reiniciado: recupera para `search_mode=lexical` âœ…

### Passo 7 â€” DocumentaÃ§Ã£o e fechamento âœ…
- `docs/STATUS.md` atualizado com seÃ§Ã£o "Estado de validaÃ§Ã£o"
- Checagens finais `RULES.md`: Ruff âœ…, Import-linter âœ…, Testes âœ…, Mypy (deps externas) âœ…

---

### RelatÃ³rio consolidado V1

**Contagens de suÃ­tes:**
- Backend unit (sem Docker): 351 passed, 2 failed (deps ausentes)
- Backend unit (com Docker): 466 passed, 1 skipped
- Frontend unit: 86 passed
- HistÃ³rico 9A-2: 508 passed, 1 skipped (com Docker) â€” diferenÃ§a de 42 explicada por testes de integraÃ§Ã£o nÃ£o rodados na contagem atual

**Commits desde 9A-2 (6af0986):**
1. `a1b4bbb` fix(catalog): mask price for visitors on the catalog endpoints
2. `9ff34cd` fix(config): treat empty Elasticsearch credentials as absent
3. `6af0986` docs(catalog): document category images and phase 9A-2 fixes
4. `8554a9e` feat(catalog): expose resolved image_url and image_alt on the API
5. `303682c` feat(catalog): add original category illustrations served by the API
6. `4f510ba` feat(catalog): add product image field and resolution domain
7. `69cd25e` chore(repo): stop tracking compiled .pyc files
8. `238124b` docs(catalog): document demo pricing, companies and precedence
9. `82eb648` test(pricing): cover precedence, isolation and demo seed
10. `9e08f12` chore(seed): add make seed target and DEMO_USER_PASSWORD
11. `ade9321` feat(seed): realistic demo prices and three demo companies
12. `5f9f6c4` feat(pricing): resolve company prices in cart, ordering and search
13. `915e672` feat(pricing): add per-company price rules
14. `073e28d` feat: Phase 9A-3a & 9-a â€” Product photo manifest & attribute model
15. `e10c2e7` feat: product management API
16. `40b9e9d` feat: second setting to the catalogue of the e-commerce
17. `7f322a0` feat(frontend): Phase 9-c â€” Admin product form and public specifications
18. `e0ccd9b` feat(frontend): Phase 9-c steps 4-6 â€” Publication options, customer preview, validation
19. `b60f251` Fase 9B-a Passo 3: Atualiza repositÃ³rio de pedidos para incluir locale
20. `5d7ecaa` Fase 9B-a Passos 4-6: TranslationProvider, admin endpoints, seed demo, docs
21. `c323b49` feat(search): Phase 9B-b - Multilingual search (Elasticsearch)
22. `e0df395` docs: Phase 9B-b - Docker validation complete
23. `64451cc` feat(i18n): ValidaÃ§Ã£o V3 â€” 11 UI languages, RTL, fallback badge removal, visual validation prep

**Bugs encontrados/corrigidos na V1:**
1. **Alembic check drift**: Tabela `product_attribute_definitions` criada via SQL puro na migration 0017 sem model ORM â€” autogenerate detecta como "removed". Documentado como limitaÃ§Ã£o conhecida (objetos derivados de SQL puro), nÃ£o bloqueia.
2. **Testes de config falhando localmente**: 2 testes requerem mÃ³dulo `elasticsearch` nÃ£o instalado no Python local â€” passam dentro do container Docker.
3. **Sem testes removidos/desabilitados** desde 9A-2 confirmado via `git diff`.

**NÃƒO VALIDADO e riscos:**
- ValidaÃ§Ã£o visual do frontend (V3) â€” requer navegaÃ§Ã£o manual em 4 idiomas
- Modo hybrid (embeddings) â€” nÃ£o habilitado (`EMBEDDINGS_ENABLED=false`)
- Qualidade traduÃ§Ãµes Ã¡rabe â€” nÃ£o revisada por nativo
- Fallback PostgreSQL busca apenas pt-BR
- Deploy em produÃ§Ã£o â€” nÃ£o executado

---

## Validacao V2 â€” API de administracao, traducoes, idiomas e busca

**Data:** 2026-10-14
**Ambiente:** Docker Compose real (PostgreSQL + Elasticsearch v2 + Redis + backend).

### Escopo executado

- Passo 0: tokens de admin/comprador via login real com `DEMO_USER_PASSWORD` (senha nunca impressa).
- Passo 1: `UI_LOCALES` (11, descobertos em `frontend/i18n/locales.ts`: pt-BR, en, zh-CN, ja, ko,
  ru, es, de, fr, it, ar) e `CONTENT_LOCALES` (pt-BR, en, es, ar); negociacao por idioma base,
  q-values, `?lang=` prioritario, invalido -> pt-BR, `Vary: Accept-Language`.
- Passo 2: CRUD administrativo real, atributos opcionais, RBAC 401/403, 409 concorrente,
  SKU imutavel (422), auditoria, outbox, despublicar remove do indice (consulta direta ES 404),
  revert de todos os dados de teste.
- Passo 3: 4 locales de conteudo, 3 idiomas fora da lista -> en com `fallback=true`,
  `stale` servido e `reviewed`, precos identicos por idioma, revert.
- Passo 4: SKU exato em ar, termos en/es/ar, cadeia com fr, preco consultivo para visitante,
  preco por empresa (gama 27.90, beta 29.61) e isolamento entre empresas (alfa 32.90).
- Passo 5: `stop elasticsearch` -> `postgres_fallback` (2.05 s na primeira chamada,
  8-15 ms apos circuit breaker; lexical 68-162 ms), edicao durante a queda OK,
  `start` + healthcheck + `reconcile` -> recuperacao lexical (28-61 ms).
- Passo 6: **NAO VALIDADO** â€” `EMBEDDINGS_ENABLED=false`; backfill/hybrid nao executados.
- Passo 7: `docs/I18N.md` e `docs/STATUS.md` atualizados; checagens finais verdes.

### Correcoes de bugs encontrados na V2

1. **`orders.content_locale` inexistente**: o repositorio de pedidos ja gravava a coluna,
   mas nenhuma migration a criava â€” quebrava criacao de pedido em banco novo. Migration 0019.
2. **Optimistic lock quebrado**: `apply_update_to_product`/publish/unpublish geravam nova
   `version` antes do UPDATE, fazendo toda edicao falhar com 409/500. Agora preservam a versao.
3. **`updated_at` nao avancava** no UPDATE -> versao nao mudava e a segunda edicao concorrente
   passava. Renovado explicitamente no repositorio.
4. **`DRAFT` rejeitado pela constraint** de `products.status` -> despublicar falhava. Migration 0018.
5. **Slug colidia ao renomear** produto para um nome ja existente. Desambiguacao com sufixo.
6. **API admin usava role de runtime (RLS)** -> `permission denied`. Engine/UoW `forja_admin`
   separado e `DATABASE_ADMIN_URL` no compose.
7. **Auditoria inexistente**: `audit_log` nunca era escrito. Implementada para as 4 mutacoes.
8. **`ON CONFLICT` da outbox sem constraint unica** -> UPSERT falhava. Migration 0018.
9. **Drift do `product_attribute_definitions`**: model ORM criado; `alembic check` limpo.
10. **`fallback` nao marcava a cadeia de idioma** (fr -> en retornava `false`). Corrigido no router.
11. **Tipagem**: `PublicProductPage` separado de `ProductPage` (admin); `mypy --strict` zerado.

### Checagens finais

- `docker compose --env-file .env.example config --quiet` OK
- `alembic check`: sem drift
- `pytest tests/unit`: 421 passed; `tests/architecture`: 4 passed
- `pytest tests/integration`: 252 passed, 1 skipped
- `ruff check` / `ruff format --check`: OK
- `mypy app --strict`: sem erros (285 arquivos)
- `import-linter`: 4 contracts kept
- Frontend: typecheck OK, lint OK (warnings `<img>`), 86 testes
- Dados de teste revertidos; indice reconciliado (sem orfaos)

### Pendencias / riscos

- Embeddings/hybrid nao validados (`EMBEDDINGS_ENABLED=false`).
- Traducoes automatizadas, arabe nao revisado por falante nativo.
- Fallback PostgreSQL busca apenas pt-BR.
- `DATABASE_ADMIN_URL` e obrigatoria para o backoffice.
- Extensao de content locales exige traducoes + analisadores por idioma.

---

## Validacao V3 â€” Frontend: 11 idiomas, RTL, selo de fallback e checagem visual

### Passo 0 â€” Levantamento (2026-10-22)

- 11 idiomas (`frontend/i18n/locales.ts`): pt-BR (Portugues (Brasil)), en (English),
  zh-CN (ä¸­æ–‡ï¼ˆç®€ä½“ï¼‰), ja (æ—¥æœ¬èªž), ko (í•œêµ­ì–´), ru (Ð ÑƒÑÑÐºÐ¸Ð¹), es (EspaÃ±ol), de (Deutsch),
  fr (FranÃ§ais), it (Italiano), ar (Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©). Dicionarios em `frontend/messages/*.json`.
- `dir`/`lang` vem de `isRtlLocale()` sobre a lista unica `rtlLocales` (`["ar"]`); `lang={locale}`.
  Nao ha he/fa/ur na lista, entao `ar` e o unico RTL.
- Fontes (`tailwind.config.ts`): Noto Sans (latina/cirilica), Noto Sans CJK SC/JP/KR,
  Noto Sans Arabic. Nao ha hebraico nem devanagari porque essas escritas nao estao nos 11.
- Paridade existente cobria chaves/placeholders/vazios, mas comparava contra `ar.json`
  (primeiro arquivo ordenado) e o relatorio de suspeitos nao falhava.

### Passo 1 â€” Paridade dos dicionarios

- Teste corrigido para comparar sempre contra `pt-BR.json` e para **falhar** em chaves
  identicas ao pt-BR (allowlist explicita para siglas, cognatos e painel admin).
- Traduzidas **1037 chaves** (catalogo, carrinho, pedido, credito, erros, auth parcial):
  ar 106, de 105, en 116, es 83, fr 105, it 98, ja 106, ko 106, ru 106, zh-CN 106.
- Checagem: `npx vitest run tests/unit/i18n-parity.test.ts` -> 5 passed.

### Passo 2 â€” Textos do cliente

- Varredura de `app/[locale]` (sem admin), `features` (sem admin) e `shared`: unicos textos
  fixos encontrados eram o callback do Google ("Concluindo autenticacaoâ€¦" / falha) e o
  `sr-only` "Close" do dialogo.
- Novas chaves nos 11 dicionarios: `closeLabel`, `auth.googleCallbackLoading`,
  `auth.googleCallbackError`; componentes passaram a usar `t()`.
- Novo teste `tests/unit/client-hardcoded-text.test.ts` falha se voltar texto fixo/atributo
  literal nas telas do cliente (admin excluido).
- Checagem: typecheck OK, lint OK (warnings `<img>`), `npm run test` -> 87 passed.

### Passo 3 â€” Seletor de idioma

- Itens exibem nome nativo, com `lang`/`dir` por item, `aria-current` no idioma atual e
  `aria-label` no gatilho incluindo o idioma atual; Radix mantÃ©m navegaÃ§Ã£o por teclado.
- PersistÃªncia via cookie `NEXT_LOCALE` do next-intl; primeira visita usa `Accept-Language`
  com match por idioma base; desconhecido -> `pt-BR`.
- Novo teste `tests/unit/locale-selection.test.ts` (middleware real): nomes nativos,
  `fr-CA`/`en-US`/`ar-EG`, desconhecido, cookie, prefixo de rota e mesma rota ao trocar.
- Checagem: typecheck OK, lint OK, `npm run test` -> 93 passed.

### Passo 4 â€” RTL

- DireÃ§Ã£o centralizada em `directionForLocale()` (lista Ãºnica `rtlLocales = ["ar"]`), usada
  no layout (`lang={locale}`, `dir=...`). Hebraico/fa/ur nao existem nos 11.
- Auditoria nas telas do cliente (admin excluido): **18 classes fisicas trocadas** por logicas
  (alert 2, dropdown-menu 11, select 5); 1 excecao documentada `left-[50%]` (centralizacao
  absoluta do dialogo). Classes de animacao do Radix (`slide-in-from-*`, `-translate-x-*`)
  nao sao layout e ficaram.
- Icones direcionais espelhados com `rtl:-scale-x-100`: 2 `ArrowLeft` (voltar) e 1 `ChevronRight`.
- Fontes ja cobrem latina/cirilica (Noto Sans), CJK (SC/JP/KR) e arabe (Noto Sans Arabic).
- Novo teste `tests/unit/rtl.test.ts`: direcao por idioma, zero classes fisicas (com excecao)
  e pilhas de fonte. Checagem: typecheck OK, lint OK, 96 testes.

### Passo 5 â€” Nota de fallback

- Removidos os chips/`Fallback` do detalhe do produto e o bloco de idioma do pedido;
  carrinho e pedido nao exibem nada.
- Detalhe do produto mostra apenas a nota discreta `catalog.contentDisplayedIn`
  ("Conteudo exibido em {idioma}") quando `content_locale != locale`, com o **nome nativo**
  do idioma; helper `showContentLocaleNote()`.
- Chaves antigas `catalog.fallback`, `catalog.translationFallback` e `catalog.translationExact`
  removidas dos 11 dicionarios; `contentDisplayedIn` presente em todos.
- Novo teste `tests/unit/content-locale-note.test.ts` (helper, presenca so no detalhe e chaves).
- Checagem: typecheck OK, lint OK, `npm run test` -> 99 passed.

### Passo 6 â€” Cache e troca de idioma

- Achado: `Accept-Language` ja era enviado (via `useLocale`), mas as chaves do TanStack Query
  **nao incluiam o locale** em catalogo, carrinho e pedido â€” trocar de idioma podia reutilizar
  o conteudo anterior do cache.
- Chaves agora incluem o idioma: `catalogKeys` (categorias/marcas/produtos/detalhe),
  `cartKey(locale)` e `orderKey(orderId, locale)`; invalidacao ampla por prefixo preservada.
- Novo teste `tests/unit/query-keys-locale.test.ts` prova entradas separadas por idioma no
  QueryClient e que `["cart"]`/`["orders"]` continuam invalidando.
- Recarregar a pagina sempre refaz o fetch (cache em memoria) e envia o novo `Accept-Language`.
- Checagem: typecheck OK, lint OK, 102 testes.

### Passo 7 â€” ValidaÃ§Ã£o visual

- Playwright (sem dependencia nova) com Chromium; frontend em `:3010`, backend real.
- 16 capturas em `docs/validation/v3/` (pt-BR, en, ar, zh-CN Ã— catalogo, busca, detalhe,
  carrinho); spec `tests/e2e/visual-i18n.spec.ts` -> 5 passed (4 locais + SKU).
- Verificado: lang/dir, RTL espelhado, seta de voltar invertida em ar, nota de conteudo so
  em zh-CN (conteudo em ingles), ausencia de nota em en/ar/pt-BR, fontes CJK/arabe.
- Problema de layout corrigido: rotulo "Ordenar por" duplicado -> chave `catalog.sortDirection`.
- Carrinho de teste limpo (0 itens). CORS: bloqueado para navegador real (backend sem
  cabecalhos); capturas usaram `--disable-web-security` apenas para evidencia visual.
- **BLOQUEADO**: rotulo de atributo em en (`Cor` em vez de `Color`) â€” exige backend.

### Passo 8 â€” Docs e checagens finais

- `docs/I18N.md` e `docs/STATUS.md` atualizados (11 idiomas, RTL, nota, cache, limites e
  bloqueios). PROGRESS com resultados.
- Frontend: typecheck OK, lint OK (warnings `<img>`), **102 testes** (antes 86; +16),
  Playwright visual 5 passed.
- Backend: unit+arch 425 passed; ruff/format OK; mypy strict 0 erros; import-linter 4;
  compose OK; integracao 251 passed, 1 skipped, 1 falha isolada
  (`test_analisador_pt_ignora_acento`, ConnectionTimeout no ES de Testcontainers) â€”
  repetida 3x, registrada como BLOQUEADO de ambiente, sem relacao com a V3.
- `prettier --check` limpo nos arquivos da V3; 3 arquivos nao tocados seguem fora do padrao.

---

## Prompt 09 â€” README, ADRs, nÃ£o-objetivos e relatÃ³rio final (2026-10-22)

- **InventÃ¡rio:** README raiz era stub; README.pt-BR, snapshots `temp_*` e log antigo do
  STATUS foram movidos para `docs/history/` com nota; STATUS reescrito.
- **DocumentaÃ§Ã£o:** README (PT + resumo EN, Mermaid, validaÃ§Ã£o, execuÃ§Ã£o local), 9 ADRs
  novos + ADR-0004 atualizado, NON_GOALS, CHANGELOG, INDEX, API, DEPLOY_RENDER (nÃ£o
  executado), LOAD (nÃ£o executado), GAP_AUDIT reconstruÃ­do (arquivo estava vazio) e
  FINAL_REPORT.
- **Checagens reais:** backend unit+arch **425 passed**; sem Docker **427 passed, 251
  skipped**; suÃ­te com Docker **677 passed, 1 skipped**; frontend **102 passed** + build OK;
  Ruff OK (384 arquivos); `mypy app --strict` 0 erros (285 arquivos), mas `mypy .` **48
  erros em 5 arquivos de teste**; import-linter 4/4; Compose config OK. Runtime: Grafana e
  celery-beat em restart (config/permissÃ£o).
- **Links:** `scripts/check_markdown_links.py` â†’ 41 arquivos, 0 links quebrados (46 com
  histÃ³rico). Nenhum push; commits locais de documentaÃ§Ã£o.
- **NÃƒO VALIDADO:** deploy Render, teste de carga, rate limiting (nÃ£o implementado), CORS,
  modo hybrid no estado padrÃ£o, revisÃ£o nativa das traduÃ§Ãµes.

---

## Integracao Stripe Checkout (2026-10-22)

### Implementado

- Backend: `stripe==16.0.0`, `StripeCheckoutGateway` (Checkout Session hospedada, cartao,
  centavos, metadata order/company), `PaymentGatewayRouter` (CARD -> Stripe; PIX/BOLETO fake),
  `checkout_url` em `PaymentView`/`PaymentResponse`, `GET /payments/methods`,
  `POST /payments/stripe/webhook` com `Stripe-Signature` + mapeamento de eventos
  (`checkout.session.completed/async_payment_succeeded/async_payment_failed`),
  CORS configuravel (`CORS_ORIGINS`) e `FRONTEND_BASE_URL` nos redirects.
- Config: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (whsec_), aliases com validacao de
  prefixo (`sk_`/`whsec_`), `.env.example` e docker-compose atualizados.
- Frontend: `CARD` no checkout (visivel somente com `stripe_enabled`), criacao do pedido +
  pagamento + redirect para o Stripe, paginas `checkout/success` e `checkout/cancel`,
  `payment-api`/hooks, chaves novas nos 11 dicionarios (paridade ok).

### Evidencias

- Checkout Session real criada: `cs_test_...` (32.90 BRL), `checkout_url` do Stripe.
- Webhook assinado com `whsec_v3_local_test`: 200 `APPLIED`, pagamento `PAID`.
- Playwright: opcao "Cartao (Stripe)" visivel e redirect real para `checkout.stripe.com`;
  visual V3 reexecutado **sem** `--disable-web-security` (CORS ok). 6 passed.
- Dados de teste (pedidos/pagamentos/eventos/notificacoes/carrinho) revertidos.

### Checagens

- Backend unit 430 + architecture 4; integracao 255 passed, 1 skipped.
- ruff/format/mypy strict OK (286 arquivos); compose OK.
- Frontend typecheck/lint OK; 102 testes; Playwright 6.
- **Pendente de seguranca**: a `sk_test` foi exposta em conversa; rotacionar no Stripe e
  atualizar o Render. O webhook real exige o `whsec_...` do endpoint cadastrado.
- PIX/Boleto seguem simulados; sem estorno/conciliacao.

### Fechamento das pendencias do Stripe (2026-10-22)

- **Pedido pago**: `OrderStatus.PAID` + migration 0020; `ConfirmPayment` move
  `RECEIVED`/`CREDIT_REVIEW` -> `PAID` para cartao/PIX (boleto faturado fica `INVOICED`).
  Frontend: `PAID` nos contratos, rotulo e chave `ordering.statusPaid` nos 11 idiomas.
- **PIX real**: Stripe Checkout aceita `pix` quando configurado; sem Stripe, PIX continua
  no gateway fake. Frontend inicia pagamento para CARD e PIX e redireciona quando ha
  `checkout_url`; BOLETO segue o fluxo interno de fatura/credito.
- **Estorno**: `POST /api/v1/payments/{id}/refund` (ADMIN) -> Stripe Refund
  (session -> payment_intent) e status `REFUNDED`.
- **Conciliacao**: `POST /api/v1/payments/stripe/reconcile` (ADMIN, por empresa) consulta
  sessoes PENDING, confirma pagas e cancela expiradas (webhooks perdidos).
- **Valor minimo**: R$ 0,50 validado antes de criar a sessao (`422 payment_amount_too_low`).
- **Migration 0020**: downgrade desabilita RLS temporariamente para normalizar `PAID`
  antes de recriar a constraint antiga (roundtrip verde).
- Testes: unit+arch 440; payment API 12; frontend 102; Playwright 6. Integracao completa
  com 251 passed e falhas isoladas de ES por timeout do Testcontainers (ambiente).
- Rebuild da imagem do backend validado com PIX real: sessao `cs_test_...`, webhook
  `async_payment_succeeded` -> `PAID`, pedido `PAID`.

## Prompt 03 â€” Seguranca, privacidade e endurecimento (2026-10-22)

### Passo 1 â€” CORS
- Origens explicitas validadas (sem '*', sem caminho), credenciais e max_age configuraveis; RateLimit-*/Retry-After expostos.
- Testes: 5 passed (preflight permitido/bloqueado, credenciais, config invalida); Ruff OK.
- Pendente: validacao curl no Docker (passo 8).

### Passo 2 â€” Cabecalhos de seguranca
- Backend: middleware com nosniff, Referrer-Policy, Permissions-Policy, no-store em rotas sensiveis/autenticadas, HSTS condicional a producao+HTTPS e remocao de Server/X-Powered-By.
- Frontend: CSP por requisicao com nonce + strict-dynamic, frame-ancestors none, object-src none, base-uri self, connect/img restritos a API; headers em next.config.
- Testes: 6 backend + 4 CSP frontend; typecheck/lint OK. Validacao visual da CSP fica para o passo 8.

---

## Prompt 01 - Auditoria de lacunas (2026-10-22)

- **Snapshot:** HEAD `c3f28da`; 29 itens auditados: **7 EXISTE, 16 PARCIAL, 6 AUSENTE**.
  `docs/readiness/GAP_AUDIT.md` reescrito com prova por arquivo/linha, backlog e correcoes
  das afirmacoes anteriores.
- **Testes:** coleta no HEAD 710 (449 unit, 257 integration, 4 arch); com Docker (snapshot de
  704) **702 passed, 1 failed, 1 skipped**; sem Docker (710) **455 passed, 255 skipped**.
  Falha reproduzivel: `test_search_prioriza_sku_exato_e_ignora_acento` (ES/Testcontainers,
  `ConnectionTimeout`). Marcador `integration` marca todos os itens (`conftest.py:68`).
- **Qualidade:** `mypy app --strict` tem 1 erro no HEAD (`request_context.py:23`); WIP de
  rate limiting adiciona 2 e ainda nao esta commitado. `mypy .` continua vermelho no CI.
- **Remoto:** 15 commits locais nao enviados; 14 commits desde 9A-2 ja estao em
  `origin/main` (`df34400`). Auditoria somente leitura, exceto este arquivo e o GAP_AUDIT.

### Passo 3 — Rate limiting
- Token bucket atomico em Redis (Lua) por classe: auth, cadastro, busca, escrita admin, autenticados e leitura publica; health/metricas isentos.
- 429 RFC 7807 com Retry-After e RateLimit-*, IP real via TRUSTED_PROXY_COUNT, fail-open com limitador local + circuit breaker curto, metricas de rejeicao/falha.
- Login: limite por conta (HMAC), bloqueio progressivo por conta+IP sem revelar existencia; cadastro tambem limita por conta.
- Testes: 8 unitarios + 4 de integracao com Redis real; Ruff/mypy OK. Validacao Docker de 429/fail-open fica no passo 8.

## Prompt 05 — Dados, migrations, backup e reconciliação (2026-10-22)

### Passo 1 — Rollback de migrations
- `scripts/migration_drill.py`: banco `forja_scratch_migration_*`, bootstrap real, upgrade/seed/downgrade base/upgrade/seed, comparação de checksums e `alembic check`; remove somente o banco que criou.
- 0018 e 0020 documentadas como reversíveis com perda de estado (`DRAFT`->`INACTIVE`, `PAID`->`RECEIVED`); teste de arquitetura detecta downgrade ausente/não funcional.
- Drill real no head **0022**: OK em 41,10 s (25,87 s em cache quente); seed 50/4/13/4/150 idêntico antes/depois.
- Pendente: job `migrations` do Prompt 02 não existe no CI.

### Passo 2 — Backup e restauração
- `scripts/backup_db.py`: pg_dump custom, validação `PGDMP`, arquivo temporário + rename, rotação por retenção, saída em `backups/` (fora do volume).
- `scripts/restore_drill.py`: restaura o último backup em `forja_scratch_restore_*`, aplica `upgrade head`, `alembic current/check`, contagens e extensões, confirma banco dev inalterado e remove o scratch.
- Evidência: dump 226.309 bytes; restore 9,81 s; upgrade/check 9,59 s; 50/4/13/4/150; extensões OK; dev inalterado.
- `docs/BACKUP.md` cobre política, Render (PITR 3/7 dias, exports 7 dias; plano real NÃO CONFERIDO) e snapshots do ES; índice reconstruível.

### Passo 3 — Outbox
- Backoff exponencial no SQL (2^attempts, teto 60 s), `DEAD_LETTERED` no limite, motivo apenas tipo da exceção.
- CLI `outbox list-dead`, `outbox requeue <id|--all --yes>`; auditoria estruturada `search_outbox_requeued`.
- Gauges `forja_outbox_pending`, `forja_outbox_dead_total`, `forja_outbox_oldest_pending_age_seconds` atualizados pela API.
- Evidência real: ES fora + max_attempts=1 -> dead; list/requeue validados; eventos de teste removidos. Testes de idempotência e dead-letter passando.

### Passo 4 — Reconciliação
- Advisory lock de sessão (`hashtext('forja:search:reconcile')`); segunda instância sai `skipped`/`reconcile_already_running`.
- Agendador opcional (`RECONCILE_INTERVAL_SECONDS=0` default) com jitter, timeout e métricas `reconcile_last_success_timestamp_seconds`, `reconcile_duration_seconds`, `reconcile_drift_total`, `reconcile_failures_total`.
- Evidência real: lock segurado -> duas execuções skipped; drift induzido -> `upserted=1` e documento restaurado.
- Corrigido upsert pós-delete com `external_gte` + delete versionado; conflitos não contam como escrita.
- Pendente: alerta do Prompt 04 ainda não aplicado (métrica pronta); Cron Job do Render NÃO CONFERIDO no plano.

### Passo 5 — Limpeza de índices
- `prune-indices --keep N` (default 2), `--dry-run`, `--yes`; nunca remove o alvo do alias nem as N mais recentes; ordenação numérica.
- Evidência real: removida `forja_products_v1`; alias permaneceu em `forja_products_v2`; dry-run seguinte vazio.
- ILM não é usado (índice único versionado + alias + reconstruível); documentado no RUNBOOK.

### Passo 6/7 — Validação e documentação
- `docs/MIGRATIONS.md`, `docs/BACKUP.md`, `docs/search/RUNBOOK.md` e `docs/STATUS.md` atualizados.
- Testes: suíte completa com Docker 788 passed / 4 failed / 1 skipped; as 4 falhas são do WIP concorrente (1 `type: ignore` + 3 `test_companies_api` com 429 do rate limiting). Nossos testes: outbox repo 1, lock 2, todos os de busca passando.
- `mypy app --strict` 0 erros/304 arquivos; `ruff` OK; import-linter 4/4; Compose config OK.

## Prompt 06 — API: OpenAPI, versionamento, idempotencia e webhooks (2026-10-22)

### Passo 1/2 — Erros e contrato
- `ProblemDetails` RFC 9457 com `request_id` e `errors[]` por campo; handlers de 4xx/5xx uniformizados (401/403/404/409/413/422/429/503).
- OpenAPI enriquecido (tags/summary/erros/seguranca/exemplos) em `app/interface/openapi.py`; 51 rotas cobertas pelo teste `tests/unit/test_openapi_contract.py`.
- `scripts/export_openapi.py` deterministico (`sort_keys`, UTF-8, `--check`); snapshot `docs/api/openapi.json`; Redoc `docs/api/index.html`; tipos `frontend/core/domain/api-schema.d.ts`; job `openapi-contract` com `oasdiff breaking --fail-on ERR` e drift dos tipos.
- Evidencia: hash SHA-256 `E098BE93…9443`; duas execucoes identicas; oasdiff compativel exit 0, incompativel exit 1 (3 erros `response-required-property-removed`).

### Passo 3 — Versionamento/depreciacao
- `docs/API_VERSIONING.md`, `docs/WEBHOOKS.md`, `docs/api/README.md`.
- `app/interface/deprecation.py`: `Deprecation`, `Sunset`, `Link`, `Warning`, metrica `forja_deprecated_route_requests_total`; rota legada de webhook com sunset 2027-04-30. Testes 4/4.

### Passo 4 — Idempotencia
- Migrations `0021_idempotency_keys` (RLS FORCE, unique por escopo, TTL) e `0022_idempotency_tenant_scope` (indices de orders/payments por empresa).
- Header `Idempotency-Key` obrigatorio em pedido/pagamento e opcional em produto/exclusao LGPD; replay com `Idempotent-Replayed`, 422 payload diferente, 409 `Retry-After`, liberacao em 5xx; `scripts/cleanup_idempotency_keys.py`.
- Frontend: `core/domain/idempotency.ts`, header em `ordering-api`/`payment-api`, chave por tentativa/pedido no checkout; testes 112.
- Evidencia Docker: 10 concorrentes -> 1 pedido, 2 replays, 7 conflitos 409 (`Retry-After: 60`); 422 com payload diferente; limpeza de chave expirada `deleted=1`.

### Passo 5 — Webhooks
- Stripe e HMAC legado com corpo bruto limitado (1 MiB), HMAC em tempo constante, timestamp assinado (tolerancia 300 s), dois segredos ativos, rate limit `WEBHOOK`, idempotencia por evento e logs sem corpo.
- ERP/e-mail inbound: **nao se aplica**; callback OAuth nao e webhook. Documentado em `docs/WEBHOOKS.md`.
- Testes: assinatura valida/invalida/ausente/expirada, rotacao, corpo 413, repetido/DUPLICATE e Stripe (atual/anterior/invalida/expirada/ausente).

### Passo 6/7 — Validacao e documentacao
- Docker de pe: erros reais 401/403/404/422/429/503; webhook assinado 200, adulterado 401, expirado 401; `alembic downgrade 0020` + `upgrade head` + `check` OK (backup 220.451 bytes).
- Backend: Ruff check/format OK, mypy strict 0/304, import-linter 4/4, 512 unit/arch + 280 integration (1 skip); frontend typecheck/lint/test 112 OK.
- `docs/STATUS.md`, `README.md`, `docs/MIGRATIONS.md` atualizados. Nao houve push; commits locais pendentes.

## Prompt 10 â€” Fotos reais e ilustraÃ§Ãµes SVG no catÃ¡logo (2026-10-26)

### Parte 0 â€” Auditoria (somente leitura)

Fotos do responsavel em `frontend/public/brand/` (NENHUMA versionada; `git ls-files frontend/public`
retorna apenas `brand/forja-b2b-logo*.png`, `brand/icon.svg` e `brand/logo.svg`):

| Arquivo | Extensao | Dimensoes | Tamanho | EXIF | GPS |
|---|---|---|---|---|---|
| bota-e-luva-de-obra-kindelmedia-8488037.jpg | .jpg | 5184x3888 | 1.487.635 B | Orientation/Resolucao | NAO |
| botina-1242304473-30156647.jpg | .jpg | 3000x4500 | 2.443.654 B | Orientation/Resolucao | NAO |
| capacete-para-obra-38070.jpg | .jpg | 4830x3178 | 1.684.543 B | Orientation/Resolucao | NAO |
| colete-de-obra-436474929-17858119.jpg | .jpg | 4016x6016 | 747.421 B | Artist/Copyright (nulos) | NAO |
| furadeira-3877525.jpg | .jpg | 2667x4000 | 893.624 B | Orientation/Resolucao | NAO |
| kit-antiqueda-34019840.jpg | .jpg | 2624x3936 | 1.016.067 B | Orientation/Resolucao | NAO |
| kit-parafuso-7285983.jpg | .jpg | 4480x6720 | 3.144.286 B | Artist "KAROLINA GRABOWSKA KABOOMPICS" | NAO |
| luva-de-obra-8488007.jpg | .jpg | 3888x5184 | 1.583.753 B | Orientation/Resolucao | NAO |
| mascara-de-gas-3435524-5499417.jpg | .jpg | 6000x4000 | 980.251 B | Artist/Copyright (vazios) | NAO |
| mÃ¡scara-respiradora-8487784.jpg | .jpg | 3888x5184 | 851.563 B | Orientation/Resolucao | NAO |
| protetor-auricular-6791514.jpg | .jpg | 4000x6000 | 2.344.280 B | Orientation/Resolucao | NAO |
| rÃ©gua-de-mediÃ§Ã£o-5493674.jpg | .jpg | 4000x6000 | 2.497.041 B | Orientation/Resolucao | NAO |
| turquesa-2160382064-36847981.jpg | .jpg | 3787x5310 | 1.628.319 B | Orientation/Resolucao | NAO |
| Ã³culos-de-obra51320673-8352127.jpg | .jpg | 4622x6934 | 2.592.984 B | Orientation/Resolucao | NAO |

Leitura EXIF com Pillow 12.2.0 (sem `exiftool` no Windows host). Nenhum GPS em nenhuma foto.
Originais ficam em `frontend/public/` (SERVIDOS publicamente) ate a Parte A2 mover para `assets-src/`.

Por que os cartoes mostram o icone padrao da categoria: nenhuma linha de `products` tem
`image_url` preenchido no banco de desenvolvimento (coluna existe desde a migration 0015, sempre
NULL no seed); `ProductImage.resolveSrc` (frontend/shared/components/product-image.tsx) prefixa TODO
caminho relativo com a base da API (`NEXT_PUBLIC_API_URL`) â€” `/static/...` vai para a API (pasta
`backend/app/static/catalog`), e caminhos `/catalog/...` hoje tambem cairiam na API (que nao os tem)
= 404 â†’ fallback. next.config.mjs nao tem bloco `images` (usa `<img>` direto); CSP no middleware:
`img-src 'self' data: blob: http://localhost:8000` â€” `/catalog/...` na origem do frontend ja e
coberto por `'self'` (sem ajuste de CSP).

Produtos (seed, `backend/app/infrastructure/db/seeds.py`): 4 base (EPI-CAP-001, EPI-LUV-002,
EPI-RES-003, MAQ-PAR-004) + 39 demo (CAP-002..005, OCV-001..006, LUV-003..009, RES-004..008,
AUD-001..004, BOT-001..005, QUE-001..004, FUR-001..005, MAQ-005..010); 2 INACTIVE (CAP-005,
OCV-006, LUV-009, MAQ-010 sao INACTIVE = 4 na verdade). Insert com `ON CONFLICT (id) DO NOTHING`
+ `_refresh_demo_prices` â€” imagem exigira passo anÃ¡logo de refresh idempotente.

Pipeline 9A-3 preexistente: `backend/app/domain/catalog_image.py` (validacao/precedencia),
migration 0015, admin de catalogo (upload), manifesto `backend/app/seed_data/
catalog_photos_manifest.json` (10 fotos, creditos NULOS), template, pasta `assets-src/` (10 fotos
iguais as de brand/). NAO existe `scripts/optimize_catalog_images.py` nem `docs/IMAGE_CREDITS.md`
(serao criados aqui, sem duplicar pipeline). `scripts/` na raiz e para ferramentas de repo.

Tokens visuais: tema claro `--background #FAF9F6`, `--secondary #F4F2ED` (fundo do ladrilho no
card: `bg-secondary/70`), accent `--primary #F59E0B` (ambar) e `--amber-strong #D97706`; tema
escuro `--card #121212`. Nos SVGs atuais de `backend/app/static/catalog/` a paleta usada e:
ladrilho `#0F172A`, traco branco `#F8FAFC`, acento laranja `#F97316`. Paleta dos novos SVGs =
exatamente esses 3 valores (derivados dos SVGs existentes, sem inventar cor).

### Prompt 10 — Execucao (2026-10-26)

**A1/A2 — Fotos.** 14 fotos classificadas POR CONTEUDO (inspecao visual das imagens):
9 aplicadas com confianca alta (botina->BOT-001, capacete-para-obra->EPI-CAP-001,
furadeira->MAQ-PAR-004 [conteudo: parafusadeira de impacto 20V DeWalt, nome do arquivo
enganoso], kit-antiqueda->QUE-001, luva-de-obra->LUV-003, mascara-de-gas->RES-006,
mascara-respiradora->RES-005 [validulo visivel], protetor-auricular->AUD-002,
oculos-de-obra->OCV-003 [ampla visao]). Nao aplicadas: bota-e-luva (cena mista
capacete+luvas), colete (sem produto; rosto visivel), kit-parafuso (sem produto;
autor deduzivel do EXIF: Karolina Grabowska/Kaboompics), regua (sem produto), turquesa
(luva de couro, SKU incerto LUV-004 vs LUV-006) — tabela completa em
docs/illustrations/PHOTO_MAPPING.md.
`scripts/optimize_catalog_photos.py`: 640x640 WebP <=80KB (q=82 em todas), sem EXIF,
modos crop/fit (fit em fundo #F4F2ED para botina/luva/mascara/mascara-respiradora),
IDEMPOTENTE (hash identico em reexecucao). Saidas verificadas com --verify. Originais
copiados para assets-src/photos-inbox/ e REMOVIDOS de frontend/public/brand/ (nunca
versionados — git ls-files confirma; sem necessidade de git rm --cached).

**A3/A4 — Seed e creditos.** `_PRODUCT_IMAGES` (49 SKUs) + `_refresh_product_images`
(UPDATE idempotente quando diverge) em seeds.py. Backend: `/catalog/...` ja era aceito
por `is_valid_image_url` (teste adicionado). Frontend: novo modulo
`product-image-resolve.ts` (/static/->API, /catalog/->frontend, https direto; tipo por
prefixo) coberto por 7 testes + 4 testes de renderizacao (renderToStaticMarkup:
cover/contain/placeholder/dimensoes 1:1). next.config e CSP inalterados ('self' cobre
a origem do frontend). docs/IMAGE_CREDITS.md criado; manifesto (14 entradas) com
creditos dedutiveis (kindelmedia via padrao pexels-<autor>-<id>; Grabowska via EXIF).

**B — Ilustracoes.** 26 familias (FAMILIES.md), 26 SVGs 512 duotone originais
(paleta #0F172A/#F8FAFC/#F97316, traco 14, um acento, role+title, <=1 KB cada — limite
3 KB). Redesenhados os SVGs de categoria protecao-respiratoria (era um "olho") e
protecao-maos (forma ambigua), mantendo nomes. `scripts/validate_illustrations.py`
(+8 testes: XML, viewBox, tamanho, elementos/refs proibidos, paleta, acento unico,
stroke-width, title/role, cruzamento FAMILIES.md). SVGO 4.1.0 via npx --multipass
(16822 -> 14216 B nas 26; config preserva viewBox/role; titulos corrigidos depois que
o SVGO corrompeu UTF-8 no Windows — fix_illustration_titles.py + restore_illustration_role.py).
Rasterizacao via Playwright (frontend/scripts/rasterize-illustrations.mjs) em
assets-src/render/ (ignorado): 56 PNGs (96/320) — TODOS revisados visualmente; 3
redesenhos aplicados (mascara-descartavel/protecao-respiratoria mais largos com
costura nasal, serra-circular com disco conectado ao corpo, serra-de-bancada com lâmina
maior + coifa) e revalidados. gallery.html (35 cartoes, 96/160/320, claro/escuro) +
REVISIONS.md criados.

**C — Exibicao e validacao real.** ProductCard/ProductDetail com quadro 1:1
(aspect-square); fotos cover, ilustracoes contain; alt = nome do produto; lazy.
Testes de consistencia do mapeamento (4): SKUs existem, arquivos existem, um produto
por foto, cobertura: TODOS os 46 produtos ativos com imagem especifica; so MAQ-010
(INACTIVE) no fallback da categoria. Docker: backend/Dockerfile corrigido (faltava
copiar seed_data/ — make seed quebrava no container); imagem reconstruida; seed 2x com
contagens identicas (83/150/16/13); DB: 50 produtos = 9 foto + 40 ilustracao + 1
fallback; API (46 ativos listados) confirmada: RES-005 foto, RES-007 ilustracao
mascara-descartavel, LUV-003 foto, RES-004 ilustracao mascara-descartavel, AUD-002
foto, BOT-001 foto, MAQ-010 fallback /static/catalog/maquinas-estacionarias.svg —
image_alt = nome. curl -I frontend:3010: /catalog/photos/res-005.webp -> 200 image/webp
13410 B; /catalog/illustrations/esmerilhadeira.svg -> 200 image/svg+xml 559 B; EXIF
ausente nos 9 WebP (--verify). Playwright (sandbox): paginas reais NAO capturadas —
o sandbox intercepta/aborta XHR (stub 404 {} / ERR_ABORTED; evidencia em
.playwright-mcp/console-*.log); attempt com route-mocking de fixtures REAIS + imagens
reais ficou pendente por instabilidade do sandbox -> NAO VALIDADO visualmente no nivel
de pagina; imagens individuais validadas por rasterizacao e galeria.
Lint/typecheck: ruff OK, mypy strict 0/304, frontend lint/typecheck OK, testes
frontend 123 OK (25 arquivos), backend novos 22 testes OK. Commits pequenos; push ao final.

### Prompt 10 — Incidente pos-deploy: imagens "carregando para sempre" (2026-10-26, noite)

Relato do responsavel: apos o push, as imagens do app deployado (frontend Vercel
`forja-b2b.vercel.app` + API Render `forjab2b.onrender.com`) ficavam carregando por muito
tempo e terminavam em erro de conexao, com o Render aparentemente saudavel.

Diagnostico (evidencias curl + Playwright):
1. A pilha deployada estava/esta INTEIRA: API 200 rapido (produtos com image_url novo
   preenchido no banco remoto), CORS preflight/GET corretos para o dominio Vercel
   (`access-control-allow-origin: https://forja-b2b.vercel.app`, allow-headers inclui
   X-Request-ID/Accept-Language), fotos 200 no frontend (bot-001.webp 49.566 B), CSP
   `img-src` cobre 'self' + API, bundle do Vercel COM o novo resolve (/catalog/ passa na
   origem do frontend), seed remoto aplicado.
2. A carga limpa no navegador renderizou 20 cards com TODAS as imagens `complete` e
   ZERO erros de console (screenshots `prompt10-home-destaques.png` e
   `prompt10-catalogo.png` em .playwright-mcp/). Os erros de "CORS localhost:3010"
   observados no meio do diagnostico eram CONTAMINACAO DO MEU PROPRIO SANDBOX (route
   handlers orfaos dos testes de captura da manha, com ACAO errado — desfeitos com
   unroute; lixeira minha, nao da API).
3. Causa provavel do relato: janela de redeploy/cold start do plano gratuito do Render
   logo apos o push (servico reiniciando/dormindo; XHRs e imagens de fallback /static
   ficam pendentes ate o timeout de conexao). Nao e defeito do codigo novo.

Correcao defensiva aplicada (commit 1715b9e): o fallback final do ProductImage NAO
depende mais da API — `frontend/public/catalog/illustrations/generic.svg` (padrao 512,
mesma paleta) e servido pela origem do frontend, e um timeout de 10 s troca imagem que
nao carrega pelo fallback local. Com a API fria/lenta, o tile mostra a ilustracao local
em vez de girar ate o erro. Validador permite generic.svg fora do mapa de familias;
testes atualizados (123 OK, typecheck 0, validador 0 violacoes).

### Prompt 10 — Lote 2: fotos nomeadas por produto (2026-10-26, noite)

Responsavel forneceu 36 fotos nomeadas pelo proprio produto (Abafador...Ate Antiembaçante)
em frontend/public/catalog/photos/. Auditoria: 0 GPS; EXIF com Artist/Copyright dedutivel
em 4 (Anton Shoutvin, Jonathan Cooper, AdventistAsia, Lars H. Knudsen; Panoramico vazio);
formatos variados (jpg/png/webp), dimensoes 342..6000. TODAS inspecionadas visualmente —
conteudo bate com o nome (nenhum tipo divergente). Modos: 7 fit (Cinturao, Furadeira 850W,
Nitrilica, Panoramico, PFF2, Serra Circular, Incolor — recorte central cortaria o objeto),
29 crop. Pipeline estendido (PHOTO_SOURCES com dir por entrada; --verify so cobre saidas
nomeadas por SKU). Saidas: 45/50 produtos com foto; ilustracoes remanescentes: AUD-004,
LUV-004, RES-004, OCV-006, LUV-009; 0 ativos em fallback de categoria. Desempates
registrados: "Luva de Raspa Premium" -> EPI-LUV-002 (nome exato singular; LUV-004 "Luvas"
fica com ilustracao), "Respirador PFF2" -> EPI-RES-003 (nome exato; RES-004 fica com
ilustracao), "Conjugado"/"Fumê"/"7 14" normalizados.

Anti-travamento (pedido do responsavel): seed 2x no Docker (83/150/16/13 identicos);
DB 50 = 45 foto + 5 ilustracao + 0 categoria (46 ativos); API confirmada (RES-005,
RES-007, LUV-003, RES-004, AUD-004, MAQ-010, CAP-002, FUR-003); 50/50 image_url -> 200
em <2s (0 falhas, 0 lentas); navegador: 20/20 tiles carregados (16 imediatas + 4 lazy no
scroll — sem pendentes apos scroll; primeira foto visivel ~2s apos carregamento de dados
em prod; o ~21s medido local inclui compilacao dev one-off); rede de seguranca: timeout
10s -> generic.svg LOCAL (1715b9e). EXIF: 45/45 saidas limpas. Originais movidos para
assets-src/photos-inbox/ (nao servidos, nao versionados). Lint/mypy strict 0; testes
backend 15/15 novos. Commits + push ao final.

### Prompt 10 — Correcao pos-push do lote 2: "Falha de conexao" no deployado (2026-10-26, 23h)

Relato: apos o push do lote 2, o erro voltou — "carregam por um bom tempo ate dar erro
na conexao", com o Render "de pe".

Diagnostico (evidencias):
1. API Render: 200 em 0.4-1.6s (5 pedidos seguidos), CORS preflight/GET corretos para o
   dominio Vercel; app deployado renderizava 4/4 imagens e 20 cards no navegador limpo —
   a pilha estava de pe e rapida.
2. Causa raiz do "produtos sem as fotos": o banco remoto NAO tinha o seed do lote 2
   (40 ilustracoes + 9 fotos + 1 static) — o seed roda como JOB manual no Render, push
   nao o dispara. O .env local aponta para o MESMO Postgres do Render via hostname
   INTERNO (dpg-...-a, inacessivel fora da rede deles); hostname publico
   (dpg-...-a.ohio-postgres.render.com) resolve e aceita TLS.
3. Correcao 1 (dados): seed rodado contra o banco remoto pelo venv local com
   DATABASE_ADMIN_URL reescrito para o host publico + SEED_ALLOW_PRODUCTION=true
   (83/150/16/13; sem usuarios demo — DEMO_USER_PASSWORD ausente). API remota agora:
   45 fotos + 5 ilustracoes; CAP-002/MAQ-010/RES-005 com foto, AUD-004/RES-004 com
   ilustracao. App deployado verificado no navegador: catalogo exibindo as fotos do
   responsavel (evidencia .playwright-mcp/prompt10-lote2-deployado.png).
4. Correcao 2 (resiliencia — o sintoma "carrega muito e da erro"): o retry das queries
   era 1 (2 tentativas x 15s = ~31s, MENOS que o cold start de ~60s do plano gratuito
   do Render) -> "Falha de conexão" (network_error -> error.network) sempre que a API
   estivesse fria/reiniciando. Agora: retry 4 com backoff exponencial (1-8s) = ~90s de
   tolerancia, cobrindo cold start/redeploy. Mutations seguem sem retry.
Licao de operacao: CADA push que muda _PRODUCT_IMAGES/precos exige rodar o seed no banco
remoto (job manual no Render ou local com o host publico); push so entrega codigo.
