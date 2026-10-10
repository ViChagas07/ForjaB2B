# Forja B2B — Busca do catálogo: guia operacional e de deploy (Fase 6)

> Última atualização: 2026-10-10. Este é o guia de operação, deploy e validação da
> busca do catálogo (Fases 2–6). O plano e a auditoria estão em `docs/search/PLAN.md`;
> o estado real das fases está em `docs/STATUS.md`.

## 1. Arquitetura em uma página

| Componente | Papel | É fonte de verdade? |
| :--- | :--- | :--- |
| **PostgreSQL** | Dados comerciais (preço, tiers, CA/estado) + hidratação autoritativa + fallback textual | **Sim** |
| **Elasticsearch** | Busca lexical (texto, SKU, autocomplete, filtros) | Não |
| **pgvector** (extensão do PostgreSQL) | Busca semântica por embeddings (384 dims) | Não |
| **Aplicação** | Funde lexical + semântico por **RRF** e hidrata da fonte de verdade | — |

- **Nunca** indexamos preço, estoque, crédito ou dado privado. Preço é sempre resolvido
  no PostgreSQL e, para visitante, é **consultivo** (`price_on_request=true`,
  `base_unit_price=null`).
- O ES e o pgvector são **derivados e reconstruíveis**; o PostgreSQL é o único dono dos dados.
- `search_mode` na resposta informa o modo real: `hybrid`, `lexical`, `semantic_postgres`
  (ES fora, vetorial ok) ou `postgres_fallback` (ambos fora, texto no Postgres). Se tudo
  falhar, a API retorna erro (nunca lista vazia silenciosa).
- Consultas que **parecem SKU** (token curto com dígito) dispensam o vetorial, preservando o
  SKU exato no topo.

## 2. Requisitos de sistema (desenvolvimento)

- **Docker Desktop** (Windows/macOS) com WSL2 ou Docker Engine (Linux).
- **Memória:** a stack completa com Elasticsearch + PostgreSQL + Redis + backend recomenda
  **≥ 6–8 GB** livres. O container do ES usa `mem_limit: 1536m` e heap `512m` em dev.
- **Linux (host):** `sudo sysctl -w vm.max_map_count=262144` (persistir em
  `/etc/sysctl.d/99-elasticsearch.conf`). Sem isso, o Elasticsearch 9 pode não iniciar.
- **Portas:** `9200` do ES é publicada **apenas no loopback** (`127.0.0.1`) — nunca na internet.

## 3. Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. **Nunca** comite `.env` nem valores reais.
Todas as chaves abaixo são lidas de `app/core/config.py` (prefixo do ambiente).

**Elasticsearch**

| Variável | Para que serve | Dev | Produção |
| :--- | :--- | :--- | :--- |
| `ELASTICSEARCH_URL` | URL do cluster | `http://elasticsearch:9200` | `https://...` (HTTPS) |
| `ELASTICSEARCH_USERNAME` / `_PASSWORD` | basic auth | usuário `elastic` | **não usar** em prod |
| `ELASTICSEARCH_API_KEY` | autenticação por API key | vazio | **obrigatória** (usuário de app) |
| `ELASTICSEARCH_VERIFY_CERTS` | verificação de certificado | `true` (ignorado sem TLS) | **`true`** |
| `ELASTICSEARCH_CA_CERTS` | CA do cluster | vazio | caminho da CA (ex.: `/certs/ca.crt`) |
| `ELASTICSEARCH_INDEX` | alias estável | `forja_products` | idem |
| `ELASTICSEARCH_INDEX_VERSION` | versão do índice | `1` | incrementar a cada rebuild |
| `ELASTICSEARCH_INDEX_REPLICAS` | réplicas | `0` (single-node) | `1`+ (multi-node) |
| `ELASTICSEARCH_ENABLED` | liga/desliga a busca | `true` | `true` |
| `ELASTICSEARCH_SEARCH_TIMEOUT_SECONDS` / `_SEARCH_MAX_RETRIES` | busca interativa (curta, **sem retries**) | `2` / `0` | ajustar |
| `ELASTICSEARCH_INDEX_TIMEOUT_SECONDS` / `_INDEX_MAX_RETRIES` | indexação/reindex/reconcile/bootstrap (longa, com retries) | `30` / `3` | ajustar |
| `ELASTICSEARCH_BULK_BATCH_SIZE` | tamanho do lote no `bulk` | `500` | ajustar |

**Busca e embeddings**

| Variável | Para que serve |
| :--- | :--- |
| `SEARCH_DEFAULT_PAGE_SIZE` / `SEARCH_MAX_PAGE_SIZE` / `SEARCH_MAX_DEEP_PAGINATION` | paginação e proteção de profundidade |
| `SEARCH_MAX_QUERY_LENGTH` | tamanho máximo do texto |
| `SEARCH_AUTOCOMPLETE_MIN_CHARS` / `SEARCH_AUTOCOMPLETE_MAX_SUGGESTIONS` | autocomplete |
| `SEARCH_CIRCUIT_BREAKER_FAILURES` / `SEARCH_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | circuit breaker do caminho lexical (pula o ES após N falhas por T s) |
| `SEARCH_REINDEX_COUNT_TOLERANCE` | tolerância de divergência de contagem na reindexação (0 = exato) |
| `EMBEDDINGS_ENABLED` | liga a busca semântica (ver §9) |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` | modelo e dimensão (`intfloat/multilingual-e5-small`, `384`) |
| `EMBEDDING_MODEL_PATH` / `EMBEDDING_ONNX_FILENAME` / `EMBEDDING_TOKENIZER_FILENAME` | artefatos do modelo |
| `EMBEDDING_BATCH_SIZE` / `EMBEDDING_CANDIDATE_LIMIT` / `EMBEDDING_RRF_K` | backfill, top-N e RRF (`k=60`) |
| `EMBEDDING_QUERY_TIMEOUT_SECONDS` | timeout do embed da consulta |
| `SEARCH_OUTBOX_MAX_ATTEMPTS` | tentativas por evento da outbox |

**Segurança/seed**

- `SEED_*` de demonstração só rodam fora de produção; em produção exigem flag explícita
  (`SEED_ALLOW_PRODUCTION`). Os dados de demo são **fictícios** (marcas inventadas, CA `DEMO-CA-*`).
- Segredos de produção vêm do **gerenciador de segredos** do provedor; nunca do Git.

## 4. Subir localmente, acessar e checar saúde

```bash
make up                      # ou: docker compose up -d
docker compose ps            # status
docker compose logs -f elasticsearch
```

- **Aplicação:** `GET /health/live` (liveness) e `GET /health/ready` (PostgreSQL + Redis).
- **Busca:** `GET /health/search` → `ok` | `degraded` | `unavailable` | `disabled`
  (nunca derruba o readiness).
- **Cluster ES (host, loopback):**
  `curl -u "elastic:$ELASTICSEARCH_PASSWORD" http://localhost:9200/_cluster/health?wait_for_status=yellow`

**Autenticação local:** rotas de catálogo e de busca são públicas; o preço do autenticado exige
um access token (login em `/api/v1/auth/login`). Sem token, a resposta usa preço consultivo.

## 5. Índice: criar, reconstruir e reverter

O CLI é one-off e roda com a role de runtime (usa a URL do app):

```bash
# 1) criar o índice versionado + alias (idempotente)
docker compose exec backend python -m app.modules.search.interface.cli bootstrap

# 2) reindexar a partir do PostgreSQL (valida contagem, troca o alias atomicamente)
docker compose exec backend python -m app.modules.search.interface.cli reindex

# 3) só contar o que seria indexado (não toca no ES)
docker compose exec backend python -m app.modules.search.interface.cli reindex --dry-run

# 4) reconciliação (faltantes/órfãos/versão) — roda no beat a cada 15 min
docker compose exec backend python -m app.modules.search.interface.cli reconcile
```

- O alias `forja_products` aponta para `forja_products_vN`; a reindexação cria uma **nova
  versão** e só troca o alias após validar a contagem. O índice anterior **permanece** para
  rollback: basta `swap_alias` de volta (mesmo comando, versão anterior).
- **Rejeições por documento ou divergência de contagem** acima de `SEARCH_REINDEX_COUNT_TOLERANCE`
  fazem o comando terminar com **código de saída ≠ 0** e **não** trocar o alias (o índice atual
  continua servindo); o motivo resumido fica em `search_reindex_batch_rejected` /
  `search_reindex_count_mismatch`. No `reconcile`, rejeições aparecem em `search_reconcile_rejected`
  e no campo `rejected` do relatório.
- **Backfill vetorial** (Fase 5):

```bash
docker compose exec backend python -m app.modules.search.interface.cli backfill-embeddings
docker compose exec backend python -m app.modules.search.interface.cli backfill-embeddings --dry-run
```

Idempotente por `content_hash`: reexecutar não duplica nem recalcula conteúdo inalterado.

## 6. Testar a busca (cada modo e o fallback)

```bash
# lexical / autocomplete
curl -s "http://localhost:8000/api/v1/search/products?q=capacete" | jq .search_mode
curl -s "http://localhost:8000/api/v1/search/products/autocomplete?q=cap" | jq
# SKU exato (dispensa o vetorial)
curl -s "http://localhost:8000/api/v1/search/products?q=CAP-001" | jq .search_mode
```

**Fallback (ES parado — nunca `down -v`):**

```bash
docker compose stop elasticsearch
curl -s "http://localhost:8000/api/v1/search/products?q=luva" | jq .search_mode   # postgres_fallback
docker compose start elasticsearch
```

**Semântico/híbrido:** requer `EMBEDDINGS_ENABLED=true`, o modelo no caminho configurado e o
pgvector (ver §9). Com ES e vetorial ativos, `search_mode` = `hybrid`.

## 7. Smoke test pós-deploy (somente leitura)

```bash
python backend/scripts/smoke_search.py --base-url https://api.exemplo.com \
  --sku CAP-001 --text capacete --semantic "protecao para solda"
# preço do autenticado (token via env para não vazar em `ps`)
SMOKE_TOKEN=<access-token> python backend/scripts/smoke_search.py --base-url https://api.exemplo.com
```

Valida: `/health/live`, `/health/search`, consulta por SKU, consulta sem acento, consulta
semântica, preço consultivo do visitante (e do autenticado, se houver token) e imprime os
**modos observados**. Não grava nem apaga nada.

## 8. Produção

### 8.1 Alvo (preenchido pelo responsável)

- **Elasticsearch:** `[PREENCHER: Elastic Cloud | VPS própria com Docker]`
- **PostgreSQL:** `[PREENCHER: provedor/serviço atual]` — **precisa suportar pgvector** (§9)
- **Backend (FastAPI):** `[PREENCHER: provedor/serviço]`

> Enquanto os campos acima forem `[PREENCHER]`, siga as **duas** trilhas abaixo: são
> independentes de provedor.

### 8.2 Trilha A — VPS própria com Docker

1. **Certs TLS** em `docker/elasticsearch/certs/`: `ca.crt`, `es-http.crt/key`,
   `es-transport.crt/key` (gerados pelo responsável; nunca no Git).
2. **Host:** `vm.max_map_count >= 262144`; firewall bloqueando `9200` para a internet
   (a base já publica só no loopback); volume persistente.
3. **Subir com o override de produção:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```
   O override liga TLS, monta os certs, aponta backend/worker para HTTPS com verificação
   de certificado ativa e API key, ajusta réplicas/memória e habilita o repositório de snapshots.
4. **Bootstrap da role/usuário de aplicação** (idempotente, privilégios mínimos sobre o alias):
   ```bash
   ES_ADMIN_URL=https://es.exemplo:9200 ES_ADMIN_USER=elastic ES_ADMIN_PASSWORD=... \
   ES_APP_PASSWORD=... ES_CA_CERTS=/caminho/ca.crt \
   bash backend/scripts/elasticsearch_bootstrap_roles.sh
   ```
   Em seguida aponte o `.env` do backend para `ELASTICSEARCH_API_KEY` (do usuário `forja_search_app`)
   e **remova** `ELASTICSEARCH_USERNAME/PASSWORD` de produção (a API key tem precedência).
5. **Índice:** `bootstrap` → `reindex` (§5).
6. **Snapshots:** registrar o repositório (`path.repo` já montado) e agendar snapshots; além do
   `pg_dump` (§10).

### 8.3 Trilha B — Elastic Cloud

1. Crie o deployment e **obtenha o endpoint HTTPS** (`ELASTICSEARCH_URL`).
2. Crie uma **API key restrita** ao alias/índice (`forja_products*`) com os privilégios
   necessários (read/write/create_index/manage/view_index_metadata + `monitor` de cluster).
   O script `backend/scripts/elasticsearch_bootstrap_roles.sh` serve de referência do conjunto
   mínimo de privilégios; no Cloud, a API key pode ser criada pelo console/API.
3. Restrinja o acesso por IP/traffic filtering quando disponível.
4. Configure `ELASTICSEARCH_URL`, `ELASTICSEARCH_API_KEY`, `ELASTICSEARCH_VERIFY_CERTS=true` e,
   se aplicável, `ELASTICSEARCH_CA_CERTS`.
5. **Não** use `docker-compose.prod.yml` neste alvo (ele é para VPS).

### 8.4 Migrations em produção (seguras)

1. **Backup antes** (§10).
2. Confirme que o provedor PostgreSQL **suporta a extensão pgvector** e que a role admin pode
   `CREATE EXTENSION`.
3. `make migrate` (one-off com a role admin). A migration `0013` habilita `vector` e cria
   `product_embeddings` + índice HNSW. As migrations `0012`/`0013` são idempotentes
   (`CREATE EXTENSION IF NOT EXISTS`).
4. Se a extensão **não** estiver disponível: **não force**. A busca continua em `lexical`
   (ES) / `postgres_fallback`; registre a pendência.

## 9. Embeddings e pgvector (busca semântica)

**Validado localmente em 2026-10-10** com o modelo real (`intfloat/multilingual-e5-small`):
backfill idempotente (41 embeddings), consulta em modo **`hybrid`** e degradação para `lexical`
sem o provedor. **Medições reais:**

- **Modelo** (MIT): `model.onnx` **448 MB** + `tokenizer.json` **16,3 MB** (medido por HEAD).
- **Runtime** `onnxruntime`+`tokenizers`+`numpy`: **+172 MB** na imagem (308 MB → **480 MB**);
  **+448 MB** se o modelo for embutido no build (total ~+620 MB).
- **Latência (CPU):** carga do modelo ~1,4 s (uma vez, no startup); embed da consulta **~7 ms**;
  consulta completa em modo `hybrid` **~50 ms** (ES + pgvector + hidratação).
- **Memória:** ~0,5 GB (pesos fp32) + overhead do runtime no backend.

- **Imagem do PostgreSQL:** `pgvector/pgvector:0.8.7-pg16` (mesma major 16; volume reaproveitado).
  **Faça backup lógico antes de trocar a imagem em ambiente com dados.**
- **Habilitar:** instale `onnxruntime`/`tokenizers`/`numpy`; baixe o modelo no build para
  `EMBEDDING_MODEL_PATH` (`model.onnx` + `tokenizer.json`; nunca em tempo de requisição) ou monte
  por volume; defina `EMBEDDINGS_ENABLED=true`; rode `backfill-embeddings`.
- **Padrão do repositório:** `EMBEDDINGS_ENABLED=false` → busca **lexical com fallback PostgreSQL**.
  Ao ser habilitado, o `search_mode` passa a **`hybrid`** quando ES e pgvector respondem.
- **Degradação:** sem modelo/dependência (ou timeout do embed) → `lexical`; sem ES → `semantic_postgres`;
  sem ambos → `postgres_fallback`.

## 10. Backups e recuperação

```bash
# PostgreSQL (lógico, para fora do volume)
docker compose exec -T postgres pg_dump -U "$POSTGRES_BOOTSTRAP_USER" -d "$POSTGRES_DB" -Fc \
  > backup_$(date +%Y%m%d_%H%M%S).dump
# Elasticsearch (snapshot para o repositório de arquivos configurado no path.repo)
# registrar o repositório e criar snapshot via API _snapshot (ver docs oficiais do ES).
```

- **Nunca** apague/recrie volumes nem use `docker compose down -v`.
- Índice é reconstruível a partir do PostgreSQL (`bootstrap` + `reindex` + `backfill-embeddings`),
  então não é fonte de verdade e não precisa de backup crítico.

## 11. Observabilidade

- **Logs estruturados (JSON):** `search_completed` traz `search_mode`, `total`, `returned` e
  `duration_ms`; `search_stale_index_entry_dropped` / `search_stale_entries_summary` registram
  desvios de sincronização; `search_primary_unavailable_switching_to_fallback` e
  `semantic_search_unavailable` registram degradações. Nada de termo buscado, tenant ou segredo.
- **Métricas Prometheus** (`/metrics`): `forja_search_requests_total{mode}`,
  `forja_search_duration_seconds{mode}`, `forja_search_fallback_total{mode}`. Labels de baixa
  cardinalidade.
- **Saúde do índice:** compare `GET /api/v1/...` (contagem no PostgreSQL) com
  `GET <es>/<alias>/_count`; divergência → rode `reconcile`. Para reconstruir do zero:
  `bootstrap`/`reindex` (índice) e `backfill-embeddings` (vetorial).

## 12. Decisões de arquitetura (para quem avalia o projeto)

- **ES nunca é fonte de verdade:** preço/estoque/CA e a autorização vêm do PostgreSQL; o índice
  devolve apenas ids, e a aplicação **hidrata** e **descarta** entradas defasadas.
- **Fallback explícito e observável:** falha de infraestrutura nunca vira lista vazia; o modo real
  é sempre informado. `postgres_fallback` usa `tsvector('portuguese')` + `unaccent` + `pg_trgm`.
- **Híbrido = dois caminhos de fato:** só se chama `hybrid` quando ES **e** pgvector respondem;
  o RRF funde e o SKU exato continua prioritário.
- **Derivados reconstruíveis:** índice versionado + alias (rollback trivial) e embeddings em
  tabela separada (regeração sem tocar nos produtos).
- Ver `docs/ADRs/0004-busca-hibrida.md`.

## 13. Limitações conhecidas

- **Ordenação por preço fora do índice** (preço não é indexado); a ordenação lexical usa
  relevância do ES com desempate por nome.
- **Sinônimos/abreviações de EPIs** não implementados (ex.: "óculos"↔"oculos" já funciona por
  `asciifolding`, mas não há dicionário de sinônimos).
- **Custo de memória do modelo** de embeddings (~0,5–1,0 GB) quando habilitado.
- **Frescura do índice** depende de reindexação/reconciliação enquanto não existir caminho de
  escrita de catálogo (backoffice) emitindo eventos no outbox.
- **Catálogo é global** (sem tenant): a busca não filtra por empresa; autorização refere-se a
  preço/visibilidade, não a um catálogo por cliente.
- **Upgrade do Elasticsearch (achado real):** um volume criado pelo ES **8.15.0** não sobe direto no
  **9.5.5** (o 9.x exige passar por **8.19.0**). Procedimento não destrutivo, no mesmo volume: subir
  `elasticsearch:8.19.0` (aguardar `healthy`), parar, e então subir `9.5.5`. Nunca remova o volume.
- **Latência durante indisponibilidade do Elasticsearch:** sem circuit breaker, cada busca tenta o ES
  (com retries do cliente) antes de cair no fallback — medido **~15 s** por requisição com o serviço
  parado. Recomendação: circuit breaker e/ou timeout de conexão curto (não implementados).
- **Fuzzy no nome** pode trazer correlações frouxas (ex.: `q=RES-008` retornou outro produto por
  similaridade); o SKU exato continua prioritário e produtos não vendáveis nunca aparecem.

## 14. Estado de validação (2026-10-10)

**Validado com evidência real (Docker disponível):** build das imagens; subida de PostgreSQL/Redis/
Elasticsearch com healthchecks (ES em loopback e recusando requisição sem credencial, HTTP 401);
backup `pg_dump`; migrations `0012`/`0013` aplicadas em banco descartável (up/down) e no dev
(extensões `vector`/`unaccent`/`pg_trgm` + índices); `bootstrap` idempotente; seed idempotente;
`reindex` (41 documentos) idempotente; contagem do índice = vendáveis no PostgreSQL; inativos
ausentes; `reconcile` corrigindo despublicação/republicação; usuário de aplicação do ES lendo mas
sem operações administrativas (403); busca lexical real (SKU no topo, acento, autocomplete, filtros,
limites, não publicados, preço consultivo/autenticado); **fallback real** com o ES parado
(`postgres_fallback`) e recuperação; suíte completa **454 passed/1 skipped**; sem Docker
**220 passed/235 skipped**; **smoke test** local aprovado; **embeddings**: backfill idempotente (41),
consulta `hybrid` real e degradação para `lexical`.

**Não validado (depende do alvo real):** deploy no provedor de produção (alvo ainda `[PREENCHER]`);
TLS + API key do Elasticsearch em produção; snapshots do ES; imagem com o modelo embutido no build
(medida, não construída no repositório); latência/memória em produção; circuit breaker (não existe —
ver limitação de latência abaixo).

## 15. Como rodar os testes

```bash
cd backend
pytest tests/unit tests/architecture -q   # rapido, sem Docker
pytest -m integration -q                  # somente integracao (exige Docker)
pytest tests/ -q                          # suite completa
```
Os testes de integração são marcados com `integration` e, **sem Docker, são pulados** com mensagem
clara (a suíte padrão termina sem erros). Ver `docs/STATUS.md` para os resultados reais.
