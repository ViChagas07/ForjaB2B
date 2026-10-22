# Forja B2B — Busca: auditoria e plano (Fase 1 de 6)

> **Documento histórico (plano da Fase 1).** Descreve o estado do repositório em
> 2026-10-10, antes das Fases 2–6. Não é o estado atual: o Elasticsearch hoje é
> 9.5.5, há `docker-compose.prod.yml`, busca multilíngue e o circuito de fallback.
> Estado atual em `docs/STATUS.md` e `docs/search/RUNBOOK.md`.

> Status original: **plano aprovado, Fase 1 concluída (auditoria, sem alteração de código)**.
> Última atualização: 2026-10-10.
> Este documento é o plano das Fases 2–6 da busca do catálogo. Ele foi produzido por
> auditoria somente-leitura do repositório; nenhuma linha de código, Compose ou migration
> foi alterada para produzi-lo.

## Escopo e arquitetura decidida

A busca do catálogo é entregue em 6 fases independentes: (1) auditoria e plano · (2) Elasticsearch
e cliente · (3) índice e sincronização · (4) busca lexical e fallback · (5) busca semântica
(PGVector) e fusão · (6) produção, documentação e fechamento.

Arquitetura:

- **PostgreSQL** é a fonte oficial dos dados comerciais (preços, estoque, crédito, autorização) **e**
  o mecanismo de fallback.
- **Elasticsearch** é o motor de busca lexical (texto, SKU, autocomplete, filtros). **Nunca é fonte de verdade.**
- **PGVector** (extensão do PostgreSQL) faz a busca semântica por embeddings.
- **Busca híbrida** = fusão por **Reciprocal Rank Fusion (RRF)** na camada de aplicação. Só é "híbrida
  lexical + vetorial" quando os dois caminhos realmente executam; em degradação, a resposta informa o modo real.

Decisões confirmadas (dono): ES alvo **9.5.5** + cliente **9.5.1**; embeddings via **ONNX Runtime**
(modelo ONNX do `multilingual-e5-small`); PostgreSQL com pgvector via **`pgvector/pgvector:0.8.7-pg16`**.

---

## 1. Estado atual (auditoria, por evidência)

### 1.1 Infra, Compose e deploy

- `docker-compose.yml` é o **único** arquivo de Compose (sem variantes/overrides). Sobe:
  `postgres:16.4-alpine`, `redis:7-alpine`, `rabbitmq:3.13-management-alpine`, `mailpit`,
  **`elasticsearch:8.15.0`** (`docker-compose.yml:141-160`; `discovery.type=single-node`,
  `xpack.security.enabled=false`, `ES_JAVA_OPTS=-Xms512m -Xmx512m`), `otel-collector`, `prometheus`,
  `grafana`, `backend`, `celery-worker`, `celery-beat`, `frontend`.
  > Nota (Fase 2 em diante): a tag foi atualizada para **`elasticsearch:9.5.5`** com segurança
  > LIGADA. O `8.15.0` acima descreve o estado no momento desta auditoria (histórico).
- Volume nomeado `forja_elasticsearch_data` já existe (`docker-compose.yml:30-31`).
- Backend/worker recebem `ELASTICSEARCH_HOST`/`ELASTICSEARCH_URL` (`docker-compose.yml:275-276`), mas **o
  código ignora essas variáveis** — `app/core/config.py` não tem campo de ES e usa `extra="ignore"`.
- `.env.example:52-55` já define `ELASTICSEARCH_HOST`/`ELASTICSEARCH_PORT`/`ELASTICSEARCH_URL`.
- `backend/Dockerfile` e `backend/Dockerfile.worker`: multi-stage `python:3.12.5-slim-bookworm`, instalação
  via `pip -r requirements.txt`, usuário não-root, `tini`, healthcheck curl. Não há PyTorch/onnxruntime hoje.
- CI: `.github/workflows/ci-backend.yml` (ruff, mypy, `lint-imports`, pytest com **Testcontainers**,
  bandit/pip-audit, docker-build); `ci-architecture.yml` (`docker compose config --quiet`, gitleaks,
  hadolint); `ci-frontend.yml`.
- Execução atual: **apenas Docker Compose local (dev)**. Não há manifesto de produção (k8s/ECS/terraform);
  `docs/STATUS.md` registra entrega backend-only.

### 1.2 Scaffold de busca — o que existe / incompleto / ausente

- `backend/app/modules/search/**`: **apenas 5 `__init__.py` com docstring** (`__init__.py`, `domain/`,
  `application/`, `infrastructure/`, `interface/`). Nenhuma classe, porta, rota ou teste. É scaffold puro.
- `docs/search/` existia **vazio** (este `PLAN.md` é o primeiro arquivo).
- **Elasticsearch no código Python: inexistente** (nenhum import, cliente ou health check).
- **pgvector / embeddings / vector / RRF: inexistente** em todo o repositório.
- **Nenhum router de busca**: `backend/app/interface/v1/router.py` registra 10 routers
  (identity, companies, catalog, credit, cart, ordering, invoicing, payment, notification, privacy) — sem search.
- **Nenhuma config de busca** em `app/core/config.py`; readiness (`app/interface/health.py` + `app/main.py`)
  cobre só `database` e `redis`.
- Frontend: só o filtro `q` do catálogo (`frontend/features/catalog/catalog-filters.tsx`, `catalog-browser.tsx`).
- Atenção: `backend/app/modules/notifications/` (plural) é scaffold vazio e órfão, nunca importado; o módulo
  **real** é `notification/` (singular, Fase 11 completa). Não confundir.

### 1.3 Mecanismo de atualização / eventos existente

- **Outbox transacional de notificações** (Fase 11, `docs/ADRs/0002-notification-outbox-celery.md`):
  - Tabela `notifications` **é** o outbox; inserção atômica via
    `app.infrastructure.db.outbox.enqueue_notification(session, ...)` dentro da **mesma transação/UoW**
    antes de `uow.commit()` (usada em `ordering/…`, `invoicing/…`, `payment/…`).
  - Dispatch por **Celery Beat a cada 10 s** → task `app.tasks.notifications.dispatch_outbox`
    (`backend/app/tasks/notifications.py`; beat schedule em `backend/app/tasks/celery_app.py`).
  - Enumeração cross-tenant via função `SECURITY DEFINER app.list_due_notifications` (role `forja_notification`, `NOLOGIN`).
  - Retry/DLQ no nível de aplicação/DB (`attempts < 5`; `FAILED` → `DEAD_LETTERED`; `SKIPPED` p/ opt-out).
  - UoW: `app/infrastructure/db/unit_of_work.py` (`SET LOCAL app.set_tenant_context`), `SqlAlchemyUnitOfWorkFactory`.
- **Pontos de mutação de produto (crítico):** o catálogo é **global e somente leitura em runtime** (sem `company_id`,
  sem RLS; `REVOKE INSERT/UPDATE/DELETE` na migration `0002`). **Não existe** caso de uso, repositório, rota ou API de
  escrita de produto — administração de catálogo é explicitamente fora de escopo (`docs/STATUS.md:68`). As únicas
  escritas são: seeds admin (`app/infrastructure/db/seeds.py`, `INSERT … ON CONFLICT DO NOTHING`), DDL das migrations
  (`alembic/versions/0002_catalog_pricing.py`) e fixtures de teste.
  ⇒ **Não há gatilho hoje para emitir evento de produto**; a sincronização dependerá de reindex + reconciliação (§3).

### 1.4 Banco de dados: versão, migrations e extensões

- PostgreSQL **major 16** (`postgres:16.4-alpine`; Testcontainers fixa `postgres:16.4-alpine` em
  `backend/tests/integration/conftest.py`).
- Migrations via **Alembic** (`backend/alembic/`). Cadeia linear `0001`→`0010` (head = `0010_notification`).
  Há um `.pyc` órfão `0011_company_approval` em `alembic/versions/__pycache__/` **sem `.py`** — artefato obsoleto.
- Extensões habilitadas no bootstrap (`docker/postgres/init-roles.sql:47-48`): `uuid-ossp`, `pgcrypto`.
  **Não** há `CREATE EXTENSION vector`, `unaccent` nem `pg_trgm` em lugar algum.
- `unaccent`/`pg_trgm` são contrib e já disponíveis na imagem oficial; **pgvector NÃO** está em `postgres:16.4-alpine`.
- RLS: o catálogo é global (sem RLS). Tabelas de tenant usam `FORCE ROW LEVEL SECURITY` + `app.current_company_id()`.

### 1.5 Escopo original do Forja sobre busca

- A documentação só cita busca como **fora de escopo**: `docs/STATUS.md:66-70` ("busca híbrida
  Elasticsearch/PostgreSQL … fora do escopo"; "módulos `search`/`rfq` existem apenas como scaffolds").
  `docs/ARCHITECTURE.md:34` repete.
- Não há spec/roadmap dedicado de busca em `docs/`. O diretório `docs/search/` sinaliza o local previsto.

### 1.6 Versões verificadas em fonte oficial

- **Elasticsearch estável atual: 9.5.5** (`https://www.elastic.co/docs/release-notes/elasticsearch`).
- **elasticsearch-py (PyPI) atual: 9.5.1** (`https://pypi.org/project/elasticsearch/`), Python ≥3.10, licença Apache-2.0.
  Regra: cliente 9.x ↔ servidor 9.x; clients são *forward compatible*; cliente 9.0.0 em servidor 8 **falha**.
- **pgvector/pgvector** (Docker Hub): tags `0.8.7-pg16`, `pg16`, `pg16-bookworm`, `pg16-trixie` — base **Debian**
  (não há variante alpine).
- **intfloat/multilingual-e5-small** (Hugging Face): licença **MIT**, **12 camadas / 384 dims**, ~0,1B params,
  multilíngue (94–100 idiomas), `model.safetensors` **471 MB** (+ `tokenizer.json` 17,1 MB +
  `sentencepiece.bpe.model` 5,07 MB ⇒ ~493 MB em fp32); há também `onnx/model_O4.onnx` publicado no repositório.
  Requer prefixos `"query: "` / `"passage: "`.

---

## 2. Modelo de dados relevante para busca

O catálogo é **global** (sem tenant): `backend/app/infrastructure/db/models/catalog.py`, migration
`alembic/versions/0002_catalog_pricing.py`.

| Tabela | Campos-chave | Uso na busca |
| :--- | :--- | :--- |
| `products` | `id`, `sku` (uniq), `name`, `slug` (uniq), `description` (Text), `status` (`ACTIVE`/`INACTIVE`), `is_epi`, `ca_number`, `ca_valid_until`, `ncm`, `unit_of_measure`, `weight_kg`, `min_order_qty`, `base_unit_price` Numeric(12,2), `currency`, `attributes` JSONB (GIN) | documento indexável; **preço/estoque/disponibilidade autoritativos NÃO ficam no ES** |
| `categories` | `id`, `name`, `slug`, `parent_id` (hierárquico), `is_active` | facetas/agregação lexical |
| `brands` | `id`, `name`, `slug` | facetas/agregação lexical |
| `product_price_tiers` | `product_id`, `min_quantity`, `max_quantity`, `unit_price`, `currency`, `valid_from`/`valid_until` | preço resolvido **no Postgres** (`app/domain/pricing.py:resolve_unit_price`) |

- **Preço:** `base_unit_price` + tiers em `product_price_tiers`; resolução em `app/domain/pricing.py`
  (`resolve_unit_price`). O módulo `catalog`, na leitura, devolve apenas `base_unit_price` (não resolve tiers).
- **Preço "consultivo" para visitante:** é regra de **apresentação no frontend**
  (`frontend/features/catalog/catalog-price.tsx` → `catalog.priceOnRequest`); as rotas `/catalog/*` são públicas e
  ainda devolvem `base_unit_price`. **Não há** coluna de "preço de visitante".
- **Estoque:** **não existe** tabela/coluna de estoque. Disponibilidade hoje = `status`, `min_order_qty` e validade de CA.
- **CA:** campos no próprio produto (`is_epi`, `ca_number`, `ca_valid_until`) + regra derivada em
  `app/domain/product_availability.py` (`ca_status`, `is_sellable`). Índice parcial
  `ix_products_ca_valid_until WHERE is_epi`.
- **Busca atual:** apenas `ILIKE %q%` sobre `name`/`sku`/`description`
  (`app/modules/catalog/infrastructure/repository.py`, `_product_conditions`). Sem FTS, sem trigram.

---

## 3. Sincronização (proposta mínima compatível com a arquitetura)

Como **não há caminho de escrita de produto**, a sincronização terá três peças:

1. **Reindex (backfill) explícito** — comando one-off com a role admin (mesmo padrão de `make migrate`): lê o
   Postgres e faz `_bulk` no ES (create/update/delete por `_id = products.id`, comparando `updated_at`). É o que
   popula o índice hoje.
2. **Outbox transacional para o futuro (pronto, sem gatilho ainda)** — nova tabela `search_outbox` (global, sem RLS,
   como o catálogo) + helper `enqueue_search_event(session, ...)` **espelhando** `app/infrastructure/db/outbox.py`,
   gravado na mesma transação/UoW de qualquer futura mutação de produto. Task Celery
   `app.tasks.search.dispatch_search_outbox` (Beat) processa com retry/DLQ no nível de DB, **sem importar internals
   de outros módulos** (o `import-linter` trata `app.modules.search` como bounded context independente).
3. **Reconciliação periódica** — task Celery que compara Postgres ↔ ES por watermark (ex.: `max(updated_at)`
   conhecido, contagens por `status`) e repara divergências. Enquanto (2) não tiver gatilho, **esta é a garantia
   real de frescor**.

**Regra de ouro:** o ES **nunca** é fonte de verdade. Os hits retornam `product_id` + campos de texto/exibição;
preço, tier e sellability (CA/status) são **hidratados no Postgres** na leitura (mesma transação de leitura do catálogo).

---

## 4. Versões propostas

| Componente | Proposta | Observação |
| :--- | :--- | :--- |
| Elasticsearch (servidor) | **`docker.elastic.co/elasticsearch/elasticsearch:9.5.5`** | subir a tag no Compose (hoje 8.15.0); manter `single-node` em dev |
| Cliente Python | **`elasticsearch==9.5.1`** | `AsyncElasticsearch`; adicionar em `backend/requirements.txt` |
| PostgreSQL + pgvector | **`pgvector/pgvector:0.8.7-pg16`** | mesma major 16; base Debian (troca de alpine→Debian) |
| Extensão vetorial | **`vector` (pgvector 0.8.7)** | `CREATE EXTENSION vector` via migration (schema de domínio) |
| Extensões auxiliares | `unaccent`, `pg_trgm` (contrib, já disponíveis) | uso no analisador / FTS de fallback |
| Modelo de embeddings | **`intfloat/multilingual-e5-small`** | MIT; 12 camadas, **384 dims**; ~493 MB fp32; prefixos `query:`/`passage:` |
| Runtime de embeddings | **ONNX Runtime** (`onnxruntime`, CPU) + `onnx/model_O4.onnx` | evita torch (~1 GB na imagem); modelo montado/baixado no build |

---

## 5. Plano por fase (2 a 6) — arquivos prováveis e riscos

### Fase 2 — Elasticsearch e cliente

- `docker-compose.yml` (tag ES → 9.5.5; ajuste opcional de `ES_JAVA_OPTS`).
- `backend/requirements.txt` (+ `elasticsearch==9.5.1`).
- `backend/app/core/config.py` (settings: `elasticsearch_url`, timeouts, `search_index_name`, flag de habilitação).
- `backend/app/modules/search/infrastructure/elasticsearch.py` (factory do client) + porta em `application/ports.py`.
- `backend/app/main.py` (composição; `app.state.search_*`); `backend/app/interface/health.py` (+ probe ES **degradável**).
- **Riscos:** breaking changes 8→9; tamanho do container; segurança em prod (dev desliga xpack); client async + timeouts.

### Fase 3 — Índice e sincronização

- Índice/template + mapping (analyzer PT-BR: lowercase + `asciifolding`; `sku` keyword; `name`/`description` text; facets).
- Migration `0011_search_outbox.py` (tabela `search_outbox`; global, sem RLS) + helper `enqueue_search_event`.
- `application/`: `IndexProduct`, `DeleteProductFromIndex`, `BulkReindex`, `ReconcileIndex`.
- `backend/app/tasks/search.py` (`dispatch_search_outbox`, `reconcile_search_index`) + beat schedule em `celery_app.py`.
- Comando de reindex (one-off admin) — Make target + entrypoint.
- **Riscos:** outbox sem gatilho hoje (frescura depende da reconciliação); idempotência/`_bulk` parcial; drift; ordem delete/update.

### Fase 4 — Busca lexical e fallback

- `application/search.py` (`SearchProducts`, `Autocomplete`); porta + adaptador ES.
- Hidratação autoritativa no Postgres (reusar `SqlAlchemyCatalogRepository`) e **mascaramento de preço para visitante**.
- `interface/router.py` (`/api/v1/search/products`), `interface/schemas.py`; registrar em `interface/v1/router.py`.
- Fallback: ES indisponível/vazio ⇒ `ILIKE` no Postgres (caminho atual); a resposta expõe o `mode` real.
- **Riscos:** relevância/tuning; paginação consistente; ES down; performance da hidratação; visibilidade/RBAC.

### Fase 5 — Busca semântica (PGVector) e fusão

- Migration: `CREATE EXTENSION vector`; tabela `product_embeddings(product_id PK/FK, embedding vector(384), model, updated_at)`
  + índice **HNSW (cosine)**.
- Runtime ONNX (loader do modelo; settings de path/flag); task de **geração de embeddings em lote** + por mudança.
- `application/semantic.py` (embed da query + top-k pgvector); **RRF na camada de aplicação** fundindo ranks
  lexical (ES) + vetorial (PG).
- Degradação explícita: sem ES ⇒ vetorial?/fallback; sem vetorial ⇒ lexical; `mode` ∈ {`hybrid`, `lexical`, `semantic`, `fallback`}.
- **Riscos:** peso/download do modelo e offline; dimensão/mismatch; ONNX em CPU; tuning do RRF; latência/memória.

### Fase 6 — Produção, documentação e fechamento

- Segurança do ES em prod (TLS + auth; segredos via gerenciador); sizing de heap.
- `docs/STATUS.md`, `docs/RUNBOOK.md`, `docs/ARCHITECTURE.md`, novo **ADR** de busca híbrida.
- Métricas/alertas (saúde do ES, lag do índice, backlog do outbox) em `app/core/metrics.py` + Grafana.
- Testes: unit + integração (Testcontainers para ES/pgvector); atualizar este `PLAN.md` conforme executado.
- **Riscos:** destino de produção indefinido (só há Compose local); custo/RAM.

---

## 6. Recursos (estimativa de memória)

**Dev local (single-node, dados pequenos)** — adicional ao stack atual:

| Componente | RSS aproximado | Nota |
| :--- | :--- | :--- |
| Elasticsearch 9 (single-node) | ~1,2–1,6 GB | heap hoje 512 MB; dev pode subir para 1 GB |
| PostgreSQL 16 + pgvector | ~200–400 MB | `shared_buffers` default; índice HNSW pequeno |
| Backend FastAPI | ~200–400 MB | `--workers 4` no Dockerfile |
| Embeddings (ONNX in-process) | +~0,5–1,0 GB no backend | ~493 MB de pesos + working set |
| (alternativa) serviço de embeddings separado | ~0,7–1,2 GB em container próprio | isola o runtime, +1 serviço no Compose |

**Total adicional da busca (dev):** ~2,5–4 GB.

**Produção (referência):** ES heap **1–2 GB** (RSS ~2–4 GB), Postgres **1–2 GB**, backend **512 MB–1 GB**,
embeddings in-process ~1 GB. Dimensionar pelo volume real do catálogo (não conhecido — ver §7).

---

## 7. Perguntas em aberto (decisão humana)

1. **Destino de produção**: hoje só existe Docker Compose local. Onde backend, banco, workers e ES rodarão em prod
   (host único, cloud gerenciada)?
2. **Orçamento de RAM** do host de destino — define o heap do ES e se os embeddings ficam in-process ou em serviço separado.
3. **Backoffice/escrita de catálogo**: será implementado (e quando)? É o que fará o outbox de busca emitir eventos —
   hoje a frescura depende da reconciliação.
4. **Modelo/idioma de embeddings**: confirmar `multilingual-e5-small` e o uso dos prefixos `query:`/`passage:`;
   haverá conteúdo em idiomas além do PT-BR?
5. **Confirmação de escopo**: preço/estoque/sellability **não** entram no índice como autoritativos (apenas hidratação
   via Postgres). OK?
6. **Volume do catálogo** (nº de produtos, atributos) — para dimensionar índice/sharding e o custo do reindex.
7. **Timing do upgrade ES 8.15 → 9.5.5** já na Fase 2, ou manter 8.x por compatibilidade operacional? (proposta: 9.5.5.)

---

## 8. Referências

- `docker-compose.yml`, `.env.example`, `backend/Dockerfile`, `backend/Dockerfile.worker`
- `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/interface/v1/router.py`, `backend/app/interface/health.py`
- `backend/app/modules/search/**` (scaffold), `backend/app/modules/catalog/**`
- `backend/app/infrastructure/db/models/catalog.py`, `backend/app/infrastructure/db/seeds.py`,
  `backend/app/infrastructure/db/outbox.py`, `backend/app/infrastructure/db/unit_of_work.py`
- `backend/alembic/versions/0002_catalog_pricing.py`, `0010_notification.py`
- `backend/app/domain/pricing.py`, `backend/app/domain/product_availability.py`
- `docker/postgres/init-roles.sql`, `docs/ADRs/0002-notification-outbox-celery.md`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`
