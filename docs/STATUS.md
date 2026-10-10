# Forja B2B — Status do Backend

> Última atualização: 2026-10-10. Este documento é a fonte de verdade do estado
> de implementação das fases. Atualize-o a cada fase concluída.

## Fases concluídas

| Fase | Escopo | Estado |
| :--- | :--- | :--- |
| 1 | Identidade e autenticação (login, JWT, Argon2id, refresh com rotação) | ✅ |
| 2 | Empresas e membros (onboarding, CNPJ, RBAC por papel) | ✅ |
| 3 | Catálogo (categorias, marcas, produtos, tiers de preço) | ✅ |
| 4 | Crédito e ledger (limite, reserva, liberação, captura, pagamento) | ✅ |
| 5 | Carrinho (validação + precificação no servidor) | ✅ |
| 6 | Pedidos (snapshot, idempotência, reserva de crédito) | ✅ |
| 7 | Faturamento (boleto simulado, captura de crédito net-zero) | ✅ |
| 8 | Frete por peso (cálculo backend, determinístico) | ✅ |
| 9 | Simulação tributária (ICMS-ST, explícita e sem inventar dados fiscais) | ✅ |
| 10 | Pagamentos e checkout (PIX/CARD/BOLETO, webhook idempotente, máquina de estados) | ✅ |
| 11 | Notificações (outbox transacional, Celery/RabbitMQ, Mailpit, preferências, DLQ) | ✅ |
| 12 | LGPD (exportação, retificação, exclusão/anonimização, consentimento, auditoria) | ✅ |
| 13 | Observabilidade, segurança final e documentação | ✅ (parcial, ver limitações) |

## Qualidade (validação executada em 2026-10-09)

| Verificador | Resultado |
| :--- | :--- |
| `pytest tests/` | **359 passed** (unidade + integração com Testcontainers) |
| `ruff check .` | ✅ sem erros |
| `ruff format --check .` | ✅ 305 arquivos formatados |
| `mypy .` (strict) | ✅ 293 arquivos sem erros |
| `import-linter` | ✅ 4 contratos mantidos, 0 quebrados |
| `docker compose config --quiet` | ✅ válido |
| Alembic (drift) | ✅ coberto por `test_persistence_migrations.py` (roundtrip upgrade/downgrade) |

> Nota de ambiente: a validação foi executada com as variáveis de
> docker-compose **removidas** do ambiente do processo (o `.env`/ambiente local
> injeta `DATABASE_URL=...@postgres:5432`, o que faria `test_defaults_de_desenvolvimento`
> falhar por sobrescrever o default). O comando exato de execução limpa está em
> `docs/RUNBOOK.md`.

## Correções e adições desta auditoria

- **Pagamentos (webhook HMAC)**: o corpo bruto agora é lido ANTES do parse
  Pydantic, garantindo que a assinatura cubra exatamente os bytes recebidos
  (antes o FastAPI podia consumir o stream). Testes novos: assinatura ausente,
  concorrência idempotente (5 webhooks simultâneos → 1 APPLIED + 4 DUPLICATE).
- **Aprovação de empresas**: endpoint `POST /api/v1/companies/{id}/approve`
  protegido por `ADMIN_API_KEY` (admin de plataforma), ativando empresa PENDING e
  admin PENDING_APPROVAL atomicamente via contexto de tenant RLS.
- **Observabilidade**: endpoint `/metrics` (Prometheus) com métricas de HTTP,
  pedidos, pagamentos e notificações; dashboard Grafana "Forja B2B Overview"
  provisionado; healthchecks para `celery-worker` e `celery-beat`.

## Limitações e pendências (sem ocultar)

- **Rotação do segredo Google exposto**: pendente do responsável no Google Cloud.
  NÃO foi realizada nesta entrega.
- **Fluxo ponta a ponta Docker nesta máquina**: o volume `postgres_data` local
  está em estado inconsistente (roles `forja_auth`/`forja_notification` ausentes
  no initdb antigo) e o `.env` local tem `POSTGRES_DB` divergente das URLs
  `DATABASE_URL`/`DATABASE_ADMIN_URL`. Isso impede o `make migrate` limpo na
  máquina; as migrations foram validadas por Testcontainers. **Não removi o
  volume** (instrução do dono). Pendência: normalizar o `.env` e re-inicializar
  os roles (RUNBOOK §4.3) para exercitar o fluxo real com Mailpit.
- **Funcionalidades fora do escopo das fases 1–13** (sem módulo): busca híbrida
  Elasticsearch/PostgreSQL, cupons, Purchase Orders, aprovação interna, RFQ,
  repetição de pedidos, documentos DANFE/XML simulados, administração de
  catálogo (escrita), importação CSV e precificação em lote. Os módulos
  `search`/`rfq` existem apenas como scaffolds.
- **Integração ponta a ponta** (frontend ↔ backend): fora do escopo desta entrega
  (backend-only).

## Busca do catálogo (Fases 1–6)

| Fase | Escopo | Estado |
| :--- | :--- | :--- |
| 1 | Auditoria e plano (`docs/search/PLAN.md`) | ✅ |
| 2 | Elasticsearch e cliente (ES 9.5.5 + `elasticsearch-py` 9.5.1) | ✅ |
| 3 | Índice e sincronização (outbox + reconciliação) | ✅ |
| 4 | Busca lexical e fallback (Postgres) | ✅ |
| 5 | Busca semântica (PGVector) e fusão por RRF | ✅ (parcial: ver limitações) |
| 6 | Produção, documentação e fechamento | ⏳ |

- **Fase 1 (2026-10-10):** auditoria somente-leitura e plano completo em `docs/search/PLAN.md`.
  Nenhum código/Compose/migration alterado.
- **Achado da auditoria:** o módulo `search` é scaffold vazio; o Elasticsearch 8.15.0 estava
  **provisionado no Compose mas não integrado** (o backend ignorava `ELASTICSEARCH_*`); não há
  pgvector nem embeddings; o catálogo é global e somente leitura em runtime (sem caminho de
  escrita de produto), então a frescura do índice dependerá de **reindex + reconciliação**.
- **Fase 2 (2026-10-10):** Elasticsearch **9.5.5** habilitado no Compose com segurança LIGADA
  (`xpack.security`, senha via `.env`), porta publicada **só em `127.0.0.1`**, volume próprio,
  `mem_limit: 1536m` e healthcheck autenticado (`_cluster/health?wait_for_status=yellow`);
  o backend **não depende** do Elasticsearch para iniciar. Cliente assíncrono oficial
  `elasticsearch[async]==9.5.1` integrado: settings `ELASTICSEARCH_*` em `core/config.py`,
  porta `SearchEngine` + adaptador (`modules/search/infrastructure/elasticsearch.py`), ciclo
  de vida no `lifespan`, mapeamento de erros para `SearchUnavailableError` e endpoint
  **`GET /health/search`** (`ok`/`degraded`/`unavailable`/`disabled`), fora do readiness.
  - **Validação executada:** `docker compose --env-file .env.example config --quiet` ✅;
    `ruff check` ✅; `ruff format --check` ✅ (308 arquivos); `mypy` strict ✅ (298 arquivos);
    `import-linter` ✅ (4/4 contratos); `pytest tests/unit tests/architecture` → **156 passed**
    (inclui 13 testes novos da busca).
  - **Não executado (limitação de ambiente):** subir o Elasticsearch no Compose e conectar o
    backend a ele — o daemon Docker não está acessível nesta máquina; a suíte de integração
    (Testcontainers) resultou em **214 errors de setup**, todos por Docker indisponível
    (não há falhas de teste). Pendência de ambiente, não de código.
  - **Pendência operacional:** adicionar as novas variáveis `ELASTICSEARCH_*` ao `.env` local
    (o arquivo atual, fora do Git, ainda não as tem). Usuário de aplicação com privilégios
    mínimos e TLS em produção ficam para a Fase 6.
- **Fase 3 (2026-10-10):** dados de demonstração e índice sincronizado.
  - **Seed:** 46 produtos fictícios de EPIs/máquinas (marcas inventadas, CA `DEMO-CA-*`),
    idempotente (UUIDs determinísticos + `ON CONFLICT DO NOTHING`) e protegido em produção
    (`SEED_ALLOW_PRODUCTION`). Inclui acentos/grafias próximas e itens inativos/indisponíveis.
  - **Índice:** versionado `forja_products_v1` + alias `forja_products`, com mapping explícito
    (`dynamic: strict`) e analisadores em português (`asciifolding`, stopwords/stemmer pt,
    `edge_ngram` de autocomplete) em `modules/search/infrastructure/indices/`.
  - **Sincronização:** outbox transacional `search_outbox` (migration `0011`, global/sem RLS)
    + helper `enqueue_search_event`; casos de uso **reindex** (lotes, validação de contagem,
    troca atômica de alias, mantém o índice anterior para rollback), **reconciliação**
    (faltantes/órfãos/versões) e **dispatch** com retry/registro; tarefas Celery
    `dispatch_search_outbox` e `reconcile_search_index` no beat; CLI
    `python -m app.modules.search.interface.cli` (`reindex [--dry-run]`, `reconcile`).
    Upsert idempotente com versionamento externo (`version = updated_at`); produtos
    inativos/indisponíveis **não** entram no índice; **nenhum preço é indexado**.
  - **Validação executada:** `docker compose --env-file .env.example config --quiet` ✅;
    `ruff check` ✅; `ruff format --check` ✅; `mypy` strict ✅ (311 arquivos);
    `import-linter` ✅ (4/4 contratos); `pytest tests/unit tests/architecture` → **179 passed**
    (23 testes novos: documento, arquivos de índice, seed, sincronização).
  - **Não executado (limitação de ambiente):** seed, migrations (`0011`), criação do índice,
    reindexação/reconciliação e a suíte de integração — o **daemon Docker não está acessível**
    nesta máquina. A suíte completa resultou em **181 passed, 220 errors** (todos erros de
    setup por Docker indisponível; nenhuma falha de teste). Os testes de integração do
    Elasticsearch (`tests/integration/test_search_index_es.py`) cobrem analisadores, upsert
    idempotente, remoção e troca de alias sobre ES real (Testcontainers) quando o Docker
    estiver disponível.
  - **Pendência operacional:** adicionar `ELASTICSEARCH_INDEX_VERSION`, `ELASTICSEARCH_INDEX_REPLICAS`
    e `SEARCH_OUTBOX_MAX_ATTEMPTS` ao `.env` local.
- **Fase 4 (2026-10-10):** busca lexical com Elasticsearch como motor principal e
  **fallback PostgreSQL**, **somente lexical (ainda não vetorial)**.
  - **Endpoints:** `GET /api/v1/search/products` (paginado, filtros por categoria,
    marca e `is_epi`) e `GET /api/v1/search/products/autocomplete` (mínimo de 2
    caracteres, no máximo 10 sugestões). Públicos, com autenticação **opcional**.
  - **DSL no Elasticsearch:** construtor dedicado na infraestrutura
    (`ElasticsearchProductIndex.search/autocomplete`); prioridade testável:
    SKU exato > prefixo de SKU > frase no nome > termos no nome (fuzziness `AUTO`,
    nunca em SKU) > marca/categoria > descrição. Filtros de publicação/disponibilidade
    **sempre** aplicados (`status=ACTIVE`, `is_available=true`), independentes do cliente.
    Paginação com limites (`SEARCH_MAX_PAGE_SIZE`, `SEARCH_MAX_DEEP_PAGINATION`) e
    tamanho máximo de texto (`SEARCH_MAX_QUERY_LENGTH`), validados na aplicação (400).
  - **Hidratação autoritativa:** o índice devolve apenas ids; os dados exibidos vêm do
    PostgreSQL (`SqlAlchemyProductReader.get_products_by_ids`), reaplicando
    `is_sellable` (status + CA). Entradas defasadas do índice são **descartadas** e
    registradas em log estruturado. **Nenhum preço é lido do índice.**
  - **Preço:** autenticado recebe o preço base; visitante recebe `price_on_request=true`
    com `base_unit_price` nulo (preço consultivo). O tenant/empresa nunca vem do cliente.
  - **Fallback:** `PostgresSearchReader` com `tsvector('portuguese')`, `unaccent` e
    `pg_trgm` (migration `0012_search_fallback_extensions.py`, extensões `contrib` +
    índices GIN). Acionado quando o ES está indisponível/erro/timeout; a resposta expõe
    `search_mode` (`lexical` ou `postgres_fallback`). "Sem resultados" permanece vazio;
    se **ambos** os motores falharem, o erro é propagado (HTTP 503), nunca lista vazia.
    Com o ES desabilitado, o próprio PostgreSQL é o motor único.
  - **Validação executada:** `docker compose --env-file .env.example config --quiet` ✅;
    `ruff check` ✅; `ruff format --check` ✅ (330 arquivos); `mypy` strict ✅ (318 arquivos);
    `import-linter --config .import-linter` ✅ (4/4 contratos); `pytest tests/unit tests/architecture`
    → **195 passed** (16 testes novos: construtor de consultas, casos de uso e fallback).
    Suíte completa → **197 passed, 230 errors** (todos erros de setup por Docker indisponível;
    nenhuma falha de teste).
  - **Não executado (limitação de ambiente):** consulta real ao Elasticsearch e o fallback
    real (parar o serviço com `docker compose stop elasticsearch`) — o **daemon Docker não
    está acessível** nesta máquina. Os testes de integração correspondentes existem e rodam
    quando houver Docker: `tests/integration/test_search_index_es.py` (ranking/acento/
    autocomplete/indisponível sobre ES real) e `tests/integration/test_search_api.py`
    (endpoint + fallback Postgres real, preço de visitante vs autenticado).
  - **Limitação documentada:** ordenação por preço está **fora de escopo** (o índice não
    contém preço); a ordenação lexical usa relevância do ES, com desempate por nome.
- **Fase 5 (2026-10-10):** busca semântica com **pgvector** e fusão **RRF**. Estado real:
  **código completo e testado em unidade; o modelo de embeddings NÃO foi adotado** (porta
  implementada), então nas consultas reais desta máquina o modo é **somente lexical**.
  - **PostgreSQL/pgvector:** imagem trocada para `pgvector/pgvector:0.8.7-pg16` (mesma major
    16) no `docker-compose.yml` e no `conftest` de integração; migration `0013_search_embeddings`
    (`CREATE EXTENSION vector` + tabela `product_embeddings` com `embedding vector(384)`,
    `content_hash`, `model`, `dimension` + índice **HNSW** `vector_cosine_ops`). Cadeia Alembic
    com **head único 0013** confirmada (`alembic heads`).
  - **Embeddings:** porta `EmbeddingProvider` + adaptador local ONNX (`infrastructure/embeddings.py`,
    `intfloat/multilingual-e5-small`, prefixos `passage:`/`query:`, pooling médio + L2, inferência
    em thread) e **import tardio** de `onnxruntime`/`tokenizers`/`numpy`. Texto embutido = nome +
    marca + categoria + descrição (**sem preço nem dado privado**); `content_hash` evita recálculo.
  - **Sincronização:** `BackfillEmbeddings` idempotente em lotes (só grava quando o hash muda;
    remove vetores órfãos/despublicados) + CLI `python -m app.modules.search.interface.cli
    backfill-embeddings [--dry-run]` + task Celery `backfill_search_embeddings` no beat; a outbox
    (Fase 3) atualiza o vetor por evento via `EmbeddingSync` (hash-aware), sem bloquear a busca
    lexical se o embedding falhar.
  - **Busca híbrida:** `SearchProducts` roda lexical (ES) e semântico (pgvector) **em paralelo**,
    funde por **RRF** (`k=60`, configurável) e degrada informando o modo real: `hybrid`,
    `lexical`, `semantic_postgres`, `postgres_fallback`; se tudo falhar, erro (nunca lista vazia).
    Consultas que parecem SKU dispensam o vetorial (preserva SKU exato no topo); o embed da
    consulta tem **timeout próprio** (`EMBEDDING_QUERY_TIMEOUT_SECONDS`). Hidratação/preço/tenant
    seguem idênticos à Fase 4 (**nada de preço vem de índice ou vetor**).
  - **Validação executada:** `docker compose --env-file .env.example config --quiet` ✅;
    `ruff check` ✅; `ruff format --check` ✅ (341 arquivos); `mypy` strict ✅ (328 arquivos);
    `import-linter --config .import-linter` ✅ (4/4); `alembic heads` ✅ (0013 head único);
    `pytest tests/unit tests/architecture` → **216 passed** (21 novos: texto/hash/pooling,
    backfill idempotente, `EmbeddingSync`, RRF/SKU e modos de degradação). Suíte completa →
    **218 passed, 1 skipped, 234 errors** (erros de setup por Docker indisponível; o skipped é o
    teste lento do modelo real; **nenhuma falha de teste**).
  - **NÃO executado / NÃO validado (limitação de ambiente — daemon Docker indisponível):**
    backup lógico (`pg_dump`) **não foi feito**; a troca de imagem e a migration 0013 **não foram
    aplicadas a um banco real**; não houve consulta real ao pgvector nem consulta `hybrid` real;
    a qualidade semântica do modelo **não foi medida**. Testes de integração prontos para rodar
    com Docker: `tests/integration/test_search_semantic_pg.py` (cosseno, idempotência, backfill
    sobre pgvector real).
  - **Decisão sobre o modelo (registrada):** o runtime (`onnxruntime` + `tokenizers`) e o download
    do modelo **não foram adicionados** ao `requirements.txt`/Dockerfile porque não foi possível
    verificar (neste ambiente) versões exatas, licença, tamanho, memória e latência em CPU sem
    inventar versões nem baixar ~493 MB sem validação — o repositório exige versões pinadas
    verificadas. `EMBEDDINGS_ENABLED=false` por padrão; a aplicação sobe em modo lexical e o
    `search_mode` reflete isso. **Procedimento de habilitação:** (1) verificar no PyPI as versões
    atuais de `onnxruntime` (CPU) e `tokenizers` e pinar em `requirements.txt`; (2) baixar
    `intfloat/multilingual-e5-small` (MIT, ~493 MB fp32; `onnx/model_O4.onnx` + `tokenizer.json`)
    no build da imagem para `EMBEDDING_MODEL_PATH`; (3) definir `EMBEDDINGS_ENABLED=true`;
    (4) rodar `backfill-embeddings` e medir latência; (5) só então declarar `hybrid`.
  - **Procedimento seguro para a troca de imagem (preserva dados):** com o stack parado, executar
    `docker compose exec -T postgres pg_dump -U "$POSTGRES_BOOTSTRAP_USER" -d "$POSTGRES_DB" -Fc
    > backup_pre_pgvector.dump` (fora do volume), subir a nova imagem (mesma major 16, volume
    reaproveitado) e rodar `alembic upgrade head`. **Não foi executado** aqui.

## Próximos passos sugeridos

1. Rotação do segredo Google (responsável).
2. Normalizar `.env` local e re-inicializar roles para exercitar `make migrate` +
   fluxo de notificação com Mailpit (`:8025`).
3. Implementar as funcionalidades fora do escopo (busca, RFQ, catálogo-escrita,
   DANFE/XML etc.) em fases futuras. A busca tem plano próprio em
   `docs/search/PLAN.md` (Fases 2–6, a partir da Fase 2: Elasticsearch e cliente).
4. Integração com o frontend (fases futuras).
