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
| `ELASTICSEARCH_REQUEST_TIMEOUT_SECONDS` / `_MAX_RETRIES` / `_BULK_BATCH_SIZE` | timeouts/limites | `5` / `3` / `500` | ajustar ao ambiente |

**Busca e embeddings**

| Variável | Para que serve |
| :--- | :--- |
| `SEARCH_DEFAULT_PAGE_SIZE` / `SEARCH_MAX_PAGE_SIZE` / `SEARCH_MAX_DEEP_PAGINATION` | paginação e proteção de profundidade |
| `SEARCH_MAX_QUERY_LENGTH` | tamanho máximo do texto |
| `SEARCH_AUTOCOMPLETE_MIN_CHARS` / `SEARCH_AUTOCOMPLETE_MAX_SUGGESTIONS` | autocomplete |
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

- **Imagem do PostgreSQL:** `pgvector/pgvector:0.8.7-pg16` (mesma major 16; volume reaproveitado).
  **Faça backup lógico antes de trocar a imagem em ambiente com dados.**
- **Modelo:** `intfloat/multilingual-e5-small` (MIT, ~493 MB fp32; ONNX `model_O4.onnx` +
  `tokenizer.json`). Deve ser **baixado no build** para `EMBEDDING_MODEL_PATH` (nunca em tempo
  de requisição) ou montado por volume.
- **Runtime:** `onnxruntime` (CPU) + `tokenizers` (+ `numpy`), importados de forma tardia.
  **Estado atual:** a dependência e o download do modelo **não estão adotados** no
  `requirements.txt`/Dockerfile — ver §12. Com `EMBEDDINGS_ENABLED=false` (padrão), a busca é
  **lexical** e o `search_mode` reflete isso.
- **Memória/latência:** prever **~0,5–1,0 GB** adicionais no backend para o modelo in-process;
  latência por consulta depende da CPU e deve ser medida no ambiente.
- **Degradação:** sem modelo/dependência (ou timeout do embed), o sistema opera em `lexical`;
  sem ES, em `semantic_postgres`; sem ambos, em `postgres_fallback`.

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

## 14. Não validado neste ambiente (Docker indisponível)

- Backup `pg_dump`, troca da imagem do PostgreSQL e aplicação das migrations `0012`/`0013` em um
  banco real.
- Subida dos serviços, build da imagem do backend, health check e consultas reais ao ES e ao
  pgvector; reindexação real; fallback real com `docker compose stop elasticsearch`.
- Smoke test contra ambiente local/produção.
- Latência e memória do modelo de embeddings.

> Itens acima estão detalhados em `docs/STATUS.md` (Fase 6).
