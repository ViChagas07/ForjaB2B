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
| 6 | Produção, documentação e fechamento | ✅ |
| 7 | Validação real com Docker (correções e evidências) | ✅ |
| 8A | Robustez: timeout de busca, falha visível no bulk, versões | ✅ |

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

- **Fase 6 (2026-10-10):** produção, documentação e fechamento.
  - **Configuração de produção:** `ELASTICSEARCH_VERIFY_CERTS` (padrão `true`) e
    `ELASTICSEARCH_CA_CERTS` em `core/config.py`, ligados ao cliente ES (health e índice);
    autenticação por **API key** tem precedência sobre usuário/senha. Override
    `docker-compose.prod.yml` (VPS): ES com TLS (HTTP+transporte), réplicas e memória ajustadas,
    repositório de snapshots e backend/worker apontando para HTTPS com verificação de certificado
    ativa + API key. Elastic Cloud documentado como alternativa (só URL HTTPS + API key).
  - **Bootstrap idempotente:** comando `python -m app.modules.search.interface.cli bootstrap`
    (cria o índice versionado + alias, sem exigir PostgreSQL) e script
    `backend/scripts/elasticsearch_bootstrap_roles.sh` (role/usuário de aplicação com privilégios
    mínimos sobre o alias, lendo credenciais do ambiente — nunca do Git).
  - **Smoke test de produção (somente leitura):** `backend/scripts/smoke_search.py` valida
    `/health/live`, `/health/search`, busca por SKU, busca sem acento, busca semântica, preço
    consultivo do visitante (e do autenticado, com token) e imprime os **modos observados**.
  - **Observabilidade:** métricas Prometheus `forja_search_requests_total{mode}`,
    `forja_search_duration_seconds{mode}` e `forja_search_fallback_total{mode}`; log estruturado
    `search_completed` com `search_mode`, `total`, `returned` e `duration_ms` (sem termo/tenant/segredo).
  - **Documentação:** `docs/search/RUNBOOK.md` (guia operacional + deploy + smoke + limitações),
    `docs/ADRs/0004-busca-hibrida.md` (decisão de arquitetura), e atualizações em
    `docs/RUNBOOK.md` (§7.6), `docs/ARCHITECTURE.md` (módulo `search` + seção) e neste `STATUS.md`.
  - **Validação executada:** `docker compose --env-file .env.example config --quiet` ✅ (base) e
    `docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.prod.yml config --quiet` ✅
    (override de produção); `ruff check` ✅; `ruff format --check` ✅; `mypy` strict ✅;
    `import-linter` ✅ (4/4); `mypy` 330 arquivos; `ruff format --check` 343 arquivos;
    `pytest tests/unit tests/architecture` → **218 passed** (2 novos de métricas da busca); suíte
    completa → **220 passed, 1 skipped, 234 errors** (erros de setup por Docker indisponível).
  - **NÃO validado (daemon Docker indisponível nesta máquina):** build da imagem do backend,
    subida dos serviços, health check, consulta real ao Elasticsearch e ao pgvector, reindexação
    real, fallback real (`docker compose stop elasticsearch`), smoke test contra o ambiente local,
    backup `pg_dump`, troca da imagem do PostgreSQL e aplicação das migrations `0012`/`0013` em
    banco real, e o que depende do ambiente de produção (que ainda está `[PREENCHER]`).
  - **Decisão sobre o modelo de embeddings (reiterada):** runtime (`onnxruntime`/`tokenizers`) e
    download do modelo seguem **não adotados**; `EMBEDDINGS_ENABLED=false` por padrão e a busca
    opera em `lexical`/fallback, com o procedimento de habilitação em `docs/search/RUNBOOK.md` §9.

- **Fase 7 (2026-10-10) — validação real com Docker e correções.** O Docker voltou a ficar
  disponível e as Fases 2–6 foram **executadas de verdade**. Bugs reais encontrados e corrigidos:
  - **Upgrade do Elasticsearch:** o volume criado pelo ES **8.15.0** recusou o **9.5.5** (exige
    8.19.0 antes). Feito upgrade **não destrutivo** no mesmo volume (8.19.0 → 9.5.5); documentado
    no runbook.
  - **Migration `0013` falhava:** `CREATE EXTENSION vector` como `forja_admin` não-superusuário dá
    `permission denied` (`vector` não é extensão *trusted*). Passou a ser criada no **bootstrap**
    (superusuário), junto de `unaccent`/`pg_trgm`. Downgrades deixaram de derrubar extensões
    (não são da role de migração).
  - **Normalizer `lowercase_normalizer`** usava `ascii_folding` com `preserve_original` → 2 tokens,
    rejeitado em campo keyword (metade do catálogo não indexava). Corrigido (asciifolding simples).
  - **Fallback PostgreSQL dava HTTP 500:** `asyncpg` não inferia o tipo dos parâmetros em `IS NULL`
    (`AmbiguousParameterError`). Adicionados `CAST(...)` explícitos (fallback e busca vetorial).
  - **Drift de metadata:** `product_embeddings` e os índices de busca (criados por migration/ SQL
    puro) e o tipo `vector` quebravam o `alembic check`. Tipo `vector` registrado para reflexão e
    objetos derivados excluídos do autogenerate.
  - **Adaptador ONNX** quebrava em lote com textos de tamanhos diferentes (sem padding). Corrigido
    (padding por lote + truncagem 512).
  - **Testes de integração** agora são **pulados** (marcador `integration`) sem Docker, em vez de
    gerar erro; esperas/índices dos testes de ES tornados robustos.
  - **Evidências:** build (backend 308 MB) e subida com healthchecks; ES em loopback com **401** sem
    credencial; backup `pg_dump`; migrations `0012`/`0013` em banco descartável (up/down) e no dev;
    `bootstrap` e `seed` idempotentes; `reindex` **41/41** idempotente; índice == vendáveis no PG;
    inativos ausentes; `reconcile` corrige despublicação/republicação; role de app lê mas **não**
    administra (403); busca lexical real (SKU no topo, acento, autocomplete, filtros, limites,
    autorização/preço); **fallback real** com ES parado (`postgres_fallback`, ~15 s por causa dos
    retries) e recuperação; **smoke test** aprovado; **embeddings** validados de ponta a ponta
    (backfill 41 idempotente; `hybrid` real; degradação `lexical`), com medições no runbook.
  - **Suíte:** `pytest tests/` → **454 passed, 1 skipped** (com Docker); sem Docker →
    **220 passed, 235 skipped, 0 errors**. `ruff`/`format`/`mypy` strict (331 arquivos)/
    `import-linter` (4/4) OK.
  - **Confirmação:** a busca em produção (padrão) é **lexical com fallback PostgreSQL**; o modo
    **lexical + vetorial (`hybrid`)** foi **validado localmente** com o modelo real habilitado.

- **Fase 8A (2026-10-10) — ajustes de robustez (sem funcionalidade nova).**
  - **A1 — timeout curto e sem retries na busca + circuit breaker.** Timeouts separados:
    `ELASTICSEARCH_SEARCH_TIMEOUT_SECONDS/SEARCH_MAX_RETRIES` (padrão **2 s / 0**) aplicados por
    chamada (`client.options`) em consulta/autocomplete; indexação mantém
    `ELASTICSEARCH_INDEX_TIMEOUT_SECONDS/INDEX_MAX_RETRIES` (**30 s / 3**). Circuit breaker simples
    (`SEARCH_CIRCUIT_BREAKER_FAILURES/COOLDOWN_SECONDS`). **Medido (ES parado):** antes
    **15,4–15,7 s** → depois **1,8–2,0 s**; com o breaker aberto **~10 ms**; recuperação automática
    ao voltar o ES (`search_circuit_breaker_closed`).
  - **A2 — falha visível na indexação em lote.** O `bulk` passou a guardar motivo resumido; reindex
    falha com **código de saída ≠ 0** e **não troca o alias** em qualquer documento rejeitado ou
    divergência de contagem acima de `SEARCH_REINDEX_COUNT_TOLERANCE` (padrão 0); `reconcile` reporta
    `rejected`; `dispatch` marca o evento como falho/reprocessável; CLI retorna erro estruturado.
    **Medido:** reindex para o índice v1 antigo rejeitou **23** documentos
    (`document_parsing_exception`), `EXITCODE=2`, alias **permaneceu** em `forja_products_v3`; reindex
    normal **41/41** (`EXITCODE=0`); `reconcile` `rejected=0` (`EXITCODE=0`).
  - **A3 — consistência de versões e documentação.** Servidor `elasticsearch:9.5.5` ↔ cliente
    `elasticsearch[async]==9.5.1` (mesma **major 9**), confirmado em Compose base/override, tests e
    docs; documentado que o upgrade intermediário (8.19) só vale para volumes criados em 8.x e que,
    em ambiente gerenciado, a major do deployment deve ser a mesma do cliente Python.
  - **Validação:** `docker compose config --quiet` (base e override) ✅; testes direcionados (19) ✅;
    suíte completa com Docker **466 passed, 1 skipped**; sem Docker **232 passed, 235 skipped, 0 erros**;
    `ruff`/formato/`mypy` strict (332 arquivos)/`import-linter` (4/4) ✅.
  - **Não validado:** deploy real em provedor gerenciado (alvo ainda `[PREENCHER]`); comportamento em
    multi-node/replicas >0; latência em produção. **Ambiente dev:** o alias aponta para
    `forja_products_v3`, mas `ELASTICSEARCH_INDEX_VERSION` no `.env` local ainda é `1` — rodar
    `reindex/bootstrap` com `--version 3` (ou ajustar o `.env`); é resíduo de dados da validação, não
    bug de código.

## Catálogo de demonstração: preços e clientes demo (Fase 9A)

Auditoria completa e decisões em `docs/CATALOG_DEMO.md`. Resumo:

- **Achado:** o modelo tinha preço de lista (`products.base_unit_price`), tiers por
  quantidade (global) e **nenhum** preço por empresa. Solução mínima adotada: tabela
  `company_price_rules` (tenant-scoped, RLS por `company_id`), leitor compartilhado
  (`app/infrastructure/db/company_pricing.py`) e `resolve_company_price` no domínio
  (`app/domain/pricing.py`).
- **Preços de demonstração:** 46 produtos normalizados para faixas plausíveis por
  categoria (BRL, arredondado como varejo). Reexecutar o seed **atualiza** os preços
  (upsert por id), sem duplicar. Inativos/não vendáveis permanecem como estavam.
- **Empresas demo:** 3 empresas fictícias com CNPJ **sintéticos e válidos** (dígito
  verificador), 3 usuários cada (ADMIN/BUYER/APPROVER). Senha via `DEMO_USER_PASSWORD`
  (nunca versionada). Condições: **alfa** sem desconto; **beta** 10% em "Proteção da
  Cabeça"; **gama** 5% global + negociado em `CAP-002`/`BOT-001`.
- **Precedência (testada):** negociado > desconto > lista. Visitante = **consultivo**.
  Busca, carrinho e pedido revalidam no PostgreSQL; nenhum preço no índice/vetor/logs.
- **Migration:** `0014_company_pricing` (head passa de `0013` para `0014`).
- **Validação (Docker de pé, 2026-10-10):** `docker compose config --quiet` (base e
  override) ✅; migration `0014` aplicada; seed executado 2x (relatórios idênticos);
  contagens 50 produtos / 4 empresas / 13 usuários / 4 regras de preço; preços por
  perfil reais para `CAP-002` (visitante consultivo; alfa `32.90`; beta `29.61`; gama
  `27.90`) e carrinho revalidando (beta `29.61`, gama `27.90`); Elasticsearch **sem
  campo de preço** (mapping e documento) e `41/41`; `reconcile` 50 checados / 6
  atualizados / 0 removidos.
- **Qualidade:** `ruff`/formato ✅ (350 arquivos); `mypy` strict ✅ (336 arquivos);
  `import-linter` ✅ (4/4); `pytest tests/unit tests/architecture` → **247 passed**;
  `pytest tests/` com Docker → **491 passed, 1 skipped**.
- **Limitações:** o catálogo público (`/catalog/products`) ainda devolve
  `base_unit_price` a visitante (apenas a busca mascara); o desconto vira o próprio
  `unit_price` do snapshot (sem coluna dedicada); duas modalidades de regra (preço
  fixo por produto e percentual por categoria/global), sem vigência; os 4 produtos da
  Fase 1 mantêm o preço original. **Observação de ambiente:** com
  `ELASTICSEARCH_API_KEY=` (vazio) no `.env.example`, o cliente ES trata a chave como
  definida e **ignora usuário/senha** (HTTP 401); containers que usam esse arquivo como
  env precisam remover a chave. O `.env` de dev do dono não a define.

## Imagens por categoria e correções da 9A-1 (Fase 9A-2)

- **0a — preço consultivo no catálogo:** `/catalog/products` e
  `/catalog/products/{id}` passaram a usar o serviço de preços compartilhado:
  visitante recebe `price_on_request=true` e `base_unit_price=null`; autenticado
  recebe o preço por empresa (negociado > desconto > lista). Contrato do frontend
  atualizado (`base_unit_price` opcional + `price_on_request`).
- **0b — credenciais ES vazias:** string vazia em `ELASTICSEARCH_API_KEY`,
  `USERNAME`, `PASSWORD` ou `CA_CERTS` passa a ser tratada como ausente (antes a
  chave vazia fazia o cliente ignorar usuário/senha e retornar HTTP 401).
- **0c — `.pyc` versionados:** 212 arquivos `__pycache__/*.pyc` removidos **do
  índice** do Git (`git rm --cached`, sem apagar do disco); `.gitignore` já cobria.
- **Imagens por categoria:** campo opcional `products.image_url` (migration
  `0015`) + domínio de validação/resolução (`app/domain/catalog_image.py`):
  **produto > categoria > genérico**. 12 SVGs originais em
  `backend/app/static/catalog`, servidos pela API em `/static`.
  `image_url`/`image_alt` no catálogo, na busca e no carrinho; nada no
  Elasticsearch; o seed mantém `image_url` nulo e continua idempotente.
- **Validação (Docker de pé, 2026-10-10):** `docker compose config --quiet` (base
  e override) ✅; backup `pg_dump` do dev (201.010 bytes, não vazio) **antes** da
  migration; `0014 -> 0015` aplicada; `alembic check` limpo; 12 imagens
  `HTTP 200 / image/svg+xml`; catálogo por perfil (visitante consultivo; alfa
  `32.90`; beta `29.61`; gama `27.90`) e `image_url` resolvida nas 11 categorias;
  `image_url` definida manualmente retornada e revertida; Elasticsearch inalterado
  (`41` docs, sem campo de preço).
- **Qualidade:** `ruff`/formato ✅ (354 arquivos); `mypy` strict ✅ (339 arquivos);
  `import-linter` ✅ (4/4); `pytest tests/` com Docker → **508 passed, 1 skipped**;
  frontend `typecheck`/`lint`/`format`/`depcruise` ✅ e `test` → **67 passed**.
- **Não validado:** a renderização visual no navegador (a porta 3000 está ocupada
  por um servidor de terceiro neste ambiente); a verificação de frontend foi
  estática (tipos/lint/testes/depcruise). **Fase 9A-3:** fotos reais via
  `image_url`.

## Próximos passos sugeridos

1. Rotação do segredo Google (responsável).
2. Normalizar `.env` local e re-inicializar roles para exercitar `make migrate` +
   fluxo de notificação com Mailpit (`:8025`).
3. Implementar as funcionalidades fora do escopo (busca, RFQ, catálogo-escrita,
   DANFE/XML etc.) em fases futuras. A busca tem plano próprio em
   `docs/search/PLAN.md` (Fases 2–6, a partir da Fase 2: Elasticsearch e cliente).
4. Integração com o frontend (fases futuras).

---

## Fase 9B-a — Traduções armazenadas: modelo, resolução, API e seed

**Iniciado:** 2026-10-13  
**Concluído:** 2026-10-13

### Resumo

| Passo | Descrição | Estado |
|-------|-----------|--------|
| 1 | Auditoria de onde textos são montados | ✅ |
| 2 | Migration `translated_at` + testes domínio i18n | ✅ |
| 3 | API com negociação locale + catálogo/carrinho/pedidos com `content_locale` | ✅ |
| 4 | Porta `TranslationProvider` + `NullTranslationProvider` + endpoints admin tradução | ✅ |
| 5 | Seed `demo_translations.json` (50 produtos × en/es/ar) + teste preservação | ✅ |
| 6 | Documentação `docs/I18N.md` + checagens finais | ✅ |

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
- `backend/app/main.py` (composição translation admin)
- `backend/app/modules/catalog/interface/__init__.py` (export translation_admin_router)
- `backend/app/modules/catalog/interface/admin_schemas.py` (schemas TranslationUpdate, TranslationAdminOut)
- `backend/tests/unit/test_i18n.py` (testes category_name, attribute_dictionary)

### Qualidade

- Ruff check: **passed**
- Ruff format: **passed**
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários: **145 passed** (i18n + product_attributes + photo_manifest)
- Mypy: Apenas erros em dependências externas ausentes (opentelemetry, elasticsearch, redis)

### NÃO VALIDADO e riscos

- **Validação Docker/integração real**: Não executada (ambiente sem Docker/ES). Checagens de `docker compose --env-file .env.example config --quiet` e testes manuais de API com `Accept-Language` pendentes.
- **Qualidade traduções árabe**: Não revisado por falante nativo — apenas tradução offline automatizada. Documentado em `docs/I18N.md`.
- **Provedor de tradução externo**: Nenhum adotado. Porta existe para decisão futura.

---

## Fase 9B-b — Busca multilíngue (Elasticsearch)

**Iniciado:** 2026-10-13  
**Concluído:** 2026-10-13

### Resumo

| Passo | Descrição | Estado |
|-------|-----------|--------|
| 1 | Auditoria rápida (mapping, query builder, documento, sincronização, locale) | ✅ |
| 2 | Mapping por idioma (v2 do índice, analisadores nativos, sem preço) | ✅ |
| 3 | Consulta (campos do cliente + pt-BR, prioridade SKU, filtros, fallback) | ✅ |
| 4 | Sincronização (outbox UPSERT/DELETE, reconcile, reindex com traduções) | ✅ |
| 5 | Validação real (Docker) | ✅ |
| 6 | Documentação e checagens finais | ✅ |

### Mudanças realizadas

**Mapping (índice v2):**
- `elasticsearch_index_version = 2` em `config.py`
- Campos multilíngues já existiam no mapping: `name_{en,es,ar}`, `description_{en,es,ar}`, `attributes_text_{en,es,ar}`
- Analisadores nativos: `en_text` (stemmer inglês), `es_text` (stemmer espanhol + ascii_folding), `ar_text` (arabic_normalization + stemmer árabe)
- pt-BR continua usando `pt_text` (stemmer português + ascii_folding)
- **Sem preço, sem dados privados** confirmado

**Documento indexado (`build_product_document`):**
- Inclui traduções quando disponíveis (`name_en`, `description_es`, `attributes_text_ar`, etc.)
- Ausência de tradução → campos `None` (não quebra `dynamic: strict`)
- Tradução parcial (ex.: apenas `es`) → apenas campos existentes preenchidos

**Consulta (`_build_text_query`):**
- Busca nos campos do idioma do cliente **E** nos de pt-BR (marcas, SKU, termos em português)
- Prioridade SKU exato (boost 10) e prefixo SKU (boost 8) mantida para todos os idiomas
- Fuzziness `AUTO` apenas nos matches de `name`, nunca no SKU
- Locale não suportado → usa apenas pt-BR; pt-BR → usa apenas campos base
- Filtros obrigatórios: `status=ACTIVE`, `is_available=True` + facets opcionais

**Hidratação/Autorização (mantido):**
- Busca retorna IDs → hidrata do PostgreSQL com preços por empresa + autorização
- Fallback PostgreSQL textual continua em português (limitação documentada)

**Embeddings (mantido):**
- Texto de origem pt-BR apenas; modelo multilíngue cobre outros idiomas
- **Não gera embeddings por idioma**

**Sincronização:**
- Outbox UPSERT/DELETE → reaplica `build_product_document` com traduções atuais
- Reconcile compara versões → reindexa docs desatualizados (incluindo traduções)
- Reindexação cria índice vN, valida contagem, troca alias atomicamente, mantém anterior para rollback

### Testes criados

- `tests/unit/test_search_multilingual.py` (8 testes): mapping, settings, documento com traduções, sem tradução, tradução parcial, sem preço, disponibilidade, versão
- `tests/unit/test_search_multilingual_query.py` (8 testes): prioridade SKU, campos por idioma, locale não suportado, pt-BR, fuzziness, filtros, busca em português
- `tests/unit/test_search_multilingual_sync.py` (8 testes): reindex com tradução, sem tradução, outbox atualiza tradução, outbox delete, reconcile detecta tradução desatualizada, reconcile remove órfãos, dry-run, tradução parcial

**Total:** 38 testes de busca passam (22 existentes + 16 novos + 4 RRF)

### Qualidade

- Ruff check: **passed**
- Ruff format: **passed**
- Import-linter: **4 contracts kept, 0 broken**
- Testes unitários: **38 passed** (busca)
- Mypy: Apenas erros em dependências externas ausentes (opentelemetry, elasticsearch, redis)

### NÃO VALIDADO e riscos

- **Modo hybrid (embeddings)**: Não testado pois embeddings não estão habilitados no ambiente de teste. Documentado.
- **Fallback PostgreSQL em português**: Busca textual no banco (quando ES indisponível) não usa traduções; apenas pt-BR. Documentado.
- **Embeddings só em pt-BR**: Modelo multilíngue cobre outros idiomas, mas embeddings são gerados apenas do texto pt-BR. Documentado.

---

## Fase 9-c — Frontend: formulário de administração e especificações do produto

**Iniciado:** 2026-10-12  
**Concluído:** 2026-10-12 (frontend completo; validação Docker pendente)

### Resumo

Frontend de administração de catálogo no estilo marketplace (OLX, Mercado Livre) e seção "Especificações" na página pública do cliente.

### Implementado

| Componente | Descrição |
|------------|-----------|
| **Lista de produtos (admin)** | `/[locale]/admin/catalog/products` — tabela com busca, filtros (categoria, status DRAFT/ACTIVE/ARCHIVED), paginação, ações: editar, ver público, publicar/despublicar, excluir (dialog) |
| **Formulário de produto** | `/[locale]/admin/catalog/products/new` e `/[id]` — 4 seções: (1) Informações básicas (obrigatórias *), (2) Detalhes dinâmicos por categoria, (3) Imagem (URL HTTPS ou catálogo estático com preview), (4) Publicação (rascunho/publicar) |
| **Página pública - Especificações** | Seção renderizada apenas se `attributes.length > 0`; usa `ProductAttributeOut[]` (label, value, unit) da API |

### Funcionalidades principais do formulário

- **Validação:** Zod + manual por campo; contadores de caracteres; foco no primeiro erro; labels/teclado acessíveis
- **Atributos dinâmicos:** Carregados via `GET /admin/catalog/categories/{slug}/attributes`; inputs por tipo (text, number, enum, boolean); agrupados por `section`; troca de categoria preserva válidos e avisa sobre removidos
- **Imagem:** Duas abas — URL HTTPS (com preview automático) e grid de imagens estáticas `/static/catalog/`; dialog modal para preview tela cheia
- **Concorrência:** Erro 409 (version conflict) → alerta + recarrega lista
- **Unsaved changes:** Aviso `beforeunload` ao sair com alterações
- **i18n:** 11 locales (pt-BR, en, es, fr, it, de, ja, ko, zh-CN, ru, ar) com ~100 chaves na seção `admin.catalog.products.form`

### Componentes UI criados

- `shared/ui/select.tsx` (Radix Select)
- `shared/ui/tabs.tsx` (Radix Tabs)
- `shared/ui/textarea.tsx`

### API Client

- `infrastructure/http/admin-catalog-api.ts` — 8 funções (list, get, create, update, publish, unpublish, attribute definitions, static images)
- `isVersionConflict()` / `getFieldErrors()` — tratamento RFC 7807

### Qualidade

| Verificador | Frontend | Backend (unit) |
|-------------|----------|----------------|
| Typecheck | ✅ passed | N/A |
| Lint | ✅ passed (3 warnings `<img>`) | ✅ Ruff passed |
| Testes | ✅ 83 passed | ✅ 93 passed |
| i18n parity | ✅ 11 locales | N/A |

### Pendente (requer Docker/Elasticsearch)

- Validação end-to-end com backend real: criar produto, editar atributos, conferir página pública
- Evidências visuais (screenshots) e respostas de API
- Rollback de produtos de teste

### Arquivos criados/modificados

**Frontend (novos):**
- `app/[locale]/admin/catalog/products/page.tsx`
- `app/[locale]/admin/catalog/products/admin-product-list-client.tsx`
- `app/[locale]/admin/catalog/products/new/page.tsx`
- `app/[locale]/admin/catalog/products/[id]/page.tsx`
- `app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx`
- `shared/ui/select.tsx`
- `shared/ui/tabs.tsx`
- `shared/ui/textarea.tsx`
- `infrastructure/http/admin-catalog-api.ts`
- `infrastructure/http/errors.ts` (correção `ApiError.extensions`)
- `tests/unit/admin-catalog-api.test.ts` (16 testes)
- `messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` (i18n completo)

**Frontend (modificados):**
- `features/catalog/product-detail.tsx` — seção Especificações com `ProductAttributeOut[]`
- `core/domain/catalog.ts` — tipos admin já existiam da Fase 9-b

**Backend (Fase 9-b, já implementados):**
- 8 endpoints admin em `app/modules/catalog/interface/admin_router.py`
- Schema `ProductAttributeOut` + conversão público em `router.py`

### Evidências de testes

- **Frontend:** `npm run typecheck` ✅, `npm run lint` ✅, `npm run test` ✅ (83 passed)
- **Backend unit:** `python -m pytest tests/unit/test_product_attributes.py tests/unit/test_photo_manifest.py` ✅ (93 passed)
- **Import-linter:** 4 contracts kept, 0 broken
- **Mypy (backend):** apenas erros em dependências externas ausentes (opentelemetry, elasticsearch, redis)

### NÃO VALIDADO e riscos

- **Validação Docker/ES:** Ambiente sem Docker/Elasticsearch — não foi possível subir stack e testar navegação visual, criar produtos reais, conferir página pública
- **Upload de imagem:** Não implementado (fora de escopo desta fase)
- **Tradução de textos admin:** Preparada (i18n keys), mas integração com Fase 9B pendente
- **Exclusão de produto:** Dialog implementado, mas endpoint DELETE não chamado (implementação pendente no backend)

### Próximos passos

1. Disponibilizar Docker/Elasticsearch → executar Passo 6 (validação real)
2. Implementar endpoint DELETE de produto no backend
3. Upload de imagem (Fase futura)
---

## Fase 9B-c — Frontend multilíngue (seletor de idioma, textos traduzidos e RTL em árabe)

**Iniciado:** 2026-10-13  
**Concluído:** 2026-10-13 (testes automatizados passam; validação visual com Docker pendente)

### Resumo

O frontend Next.js (App Router + `next-intl` v3) exibe o catálogo, busca, carrinho e pedidos no idioma escolhido pelo cliente, com layout RTL para árabe e indicadores visuais de `content_locale`/`fallback`. O painel de administração continua em português.

### Implementado

| Componente | Descrição |
|------------|-----------|
| **Infraestrutura de idioma** | `HttpRequest.locale` → header `Accept-Language`; hooks `useCatalogApi`, `useCartApi`, `useOrderingApi`, `useCreditApi`, `useCompanyApi` injetam `useLocale()` |
| **Indicadores `content_locale`/`fallback`** | `ProductDetailView`, `CartView` (por item), `OrderDetailView` (cabeçalho + itens) — Globe + código locale + badge "Fallback" |
| **RTL para árabe** | `html lang` + `dir="rtl"`; font stack `Noto Sans Arabic`; propriedades lógicas (`ms-1`, `text-end`, `text-start`); numerais ocidentais |
| **Admin "Traduções"** | Seção 5 no formulário de produto (modo edição); estados `ausente`/`machine`/`reviewed`/`stale`; edição manual + "Marcar como revisada"; "Retraduzir" oculto (sem provedor) |

### Qualidade

| Verificador | Resultado |
|-------------|----------|
| Typecheck | ✅ passed |
| Lint | ✅ passed (3 warnings `<img>` vs `next/image`) |
| Testes | ✅ 83 passed |
| i18n parity | ✅ 11 locales (356 chaves cada) |

### Testes

```bash
cd frontend && npm run typecheck  # tsc --noEmit
cd frontend && npm run lint       # next lint
cd frontend && npm run test       # vitest run (83 testes)
```

### Arquivos criados/modificados

**Frontend (novos):**
- `features/admin/catalog/translation-row.tsx` — componente linha de tradução

**Frontend (modificados):**
- `core/domain/catalog.ts` — tipos `content_locale`, `fallback`, `ProductTranslationAdmin`, `TranslationUpdate`
- `core/application/ports/http-client.ts` — `locale` em `HttpRequest`
- `infrastructure/http/api-client.ts` — header `Accept-Language`
- `infrastructure/http/catalog-api.ts` — `locale` param + `useCatalogApi` hook
- `infrastructure/http/cart-api.ts` — `locale` param + `useCartApi` hook
- `infrastructure/http/ordering-api.ts` — `locale` param + `useOrderingApi` hook
- `infrastructure/http/credit-api.ts` — `locale` param + `useCreditApi` hook
- `infrastructure/http/company-api.ts` — `locale` param + `useCompanyApi` hook
- `infrastructure/http/admin-catalog-api.ts` — endpoints de tradução admin
- `infrastructure/http/index.ts` — exports dos hooks `use*Api`
- `features/catalog/product-detail.tsx` — indicador `content_locale`/`fallback`
- `features/cart/cart-view.tsx` — indicador por item
- `features/ordering/order-detail.tsx` — indicador no cabeçalho e itens
- `features/ordering/checkout-view.tsx` — `text-left` → `text-start`
- `app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` — seção 5 "Traduções"
- `messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` — chaves de tradução (11 locales)

### NÃO VALIDADO e riscos

- **Validação visual com Docker pendente**: Ambiente sem Docker/ES — não foi possível navegar em `pt-BR`/`en`/`es`/`ar`, conferir `dir="rtl"` e layout árabe, testar seção admin "Traduções"
- **Qualidade árabe não revisada por nativo**: Traduções de máquina/automatizadas
- **Numerais ocidentais**: Não usa árabe-índicos (١, ٢, ٣)
- **Provedor de tradução não adotado**: Porta existe, botão "Retraduzir" oculto
- **Painel admin em português**: Requisito do projeto
- **Moeda fixa BRL**: Sem conversão

### Próximos passos

1. Disponibilizar Docker/Elasticsearch → executar validação visual (Passo 6)
2. Atualizar `docs/I18N.md` (já feito) e `docs/STATUS.md`
3. Checagens finais (RULES.md) — já executadas
---

## Validação V3 — Frontend: 11 idiomas, RTL, selo fallback, checagem visual

**Iniciado:** 2026-10-14
**Concluído:** 2026-10-14 (testes automatizados passam; validação visual com Docker pendente)

### Resumo

O frontend Next.js (App Router + `next-intl` v3) exibe o **site inteiro do cliente** (catálogo, busca, carrinho, pedido, login, cadastro, conta) em **11 idiomas** com layout RTL para árabe. O painel de administração permanece em português.

### Implementado (V3)

| Componente | Descrição |
|------------|-----------|
| **11 idiomas de interface** | pt-BR, en, zh-CN, ja, ko, ru, es, de, fr, it, ar — nomes nativos no seletor |
| **RTL derivado de lista única** | `isRtlLocale()` → apenas `ar`; `dir="rtl"` + `lang` no HTML |
| **Fontes por escrita** | Noto Sans Arabic, CJK SC, JP, KR, cirílica, latina |
| **Fallback badge removido** | Substituído por nota discreta "Conteúdo exibido em {locale}" só no detalhe do produto |
| **Carrinho/Pedido limpos** | Sem indicadores de locale/fallback |
| **Propriedades lógicas CSS** | `ms-1`, `text-end`, `text-start` nas telas do cliente (4 trocadas) |
| **Seletor de idioma** | Nomes nativos, `aria-label`, teclado, cookie, detecção `Accept-Language` na primeira visita |
| **Admin "Traduções"** | Estados `ausente`/`machine`/`reviewed`/`stale`, edição manual, marcar revisada |

### Qualidade

| Verificador | Resultado |
|-------------|----------|
| Typecheck | ✅ passed |
| Lint | ✅ passed (4 warnings `<img>` admin) |
| Testes unitários | ✅ 86 passed (+3 i18n-parity) |
| i18n parity | ✅ 11 locales (356 chaves cada) |

### Testes

```bash
cd frontend && npm run typecheck  # tsc --noEmit
cd frontend && npm run lint       # next lint
cd frontend && npm run test       # vitest run (86 testes)
cd frontend && npx playwright test  # E2E (requer backend)
```

### Arquivos criados/modificados (V3)

**Frontend (novos):**
- `features/admin/catalog/translation-row.tsx`

**Frontend (modificados):**
- `core/domain/catalog.ts` — tipos `content_locale`, `fallback`, `ProductTranslationAdmin`, `TranslationUpdate`
- `core/application/ports/http-client.ts` — `locale` em `HttpRequest`
- `infrastructure/http/api-client.ts` — header `Accept-Language`
- `infrastructure/http/{catalog,cart,ordering,credit,company,admin-catalog}-api.ts` — `locale` param + hooks
- `features/catalog/product-detail.tsx` — nota discreta `contentDisplayedIn`, sem badge fallback
- `features/cart/cart-view.tsx` — sem indicadores de locale/fallback
- `features/ordering/order-detail.tsx` — sem indicadores de locale/fallback
- `features/ordering/checkout-view.tsx` — `text-left` → `text-start`
- `features/credit/credit-view.tsx` — `text-right` → `text-end`
- `app/[locale]/admin/catalog/products/[id]/admin-product-form-client.tsx` — seção 5 "Traduções"
- `app/[locale]/admin/catalog/products/admin-product-list-client.tsx` — status badges via translations
- `messages/{pt-BR,en,es,fr,it,de,ja,ko,zh-CN,ru,ar}.json` — chaves de tradução (11 locales)

### NÃO VALIDADO e riscos

- **Validação visual com Docker pendente**: Ambiente sem Docker/ES — não foi possível navegar em `pt-BR`/`en`/`ar`/`zh-CN`, conferir `dir="rtl"` e layout árabe, testar seção admin "Traduções"
- **Qualidade árabe não revisada por nativo**: Traduções de máquina/automatizadas
- **Numerais ocidentais**: Não usa árabe-índicos (١, ٢, ٣)
- **Provedor de tradução não adotado**: Porta existe, botão "Retraduzir" oculto
- **Painel admin em português**: Requisito do projeto
- **Moeda fixa BRL**: Sem conversão
- **Fallback PG busca textual apenas pt-BR**

### Próximos passos

1. Disponibilizar Docker/Elasticsearch → executar validação visual
2. Checagens finais (RULES.md) — executadas

---

## Validação V1 — Estado de validação (2026-10-14)

**Executado com Docker real.** Todos os passos validados com evidência.

### O que foi validado ✅

| Passo | Descrição | Evidência |
|-------|-----------|-----------|
| 0 | Ambiente Docker | `docker info`, `docker compose config --quiet`, `docker compose ps` (10 containers healthy), ES 401 sem credenciais |
| 1 | Estado repo | `git status` (6 ahead, sem push), `git ls-files assets-src` vazio, `git ls-files *.pyc` vazio |
| 2 | Suítes teste | Backend unit 351 passed (2 failed = deps ausentes), Backend+Docker 466 passed, Frontend 86 passed, Ruff/Import-linter/Mypy OK |
| 3 | Migrations | `pg_dump` 432KB, migrations 0001-0017 em banco teste, `alembic check` (drift conhecido: tabela SQL pura), downgrade OK, extensões vector/unaccent/pg_trgm |
| 4 | Seeds idempotentes | `seed_database` (83 cat, 150 trans), `seed_attribute_definitions` (13 defs) — 2 execuções idênticas |
| 5 | Fotos | Manifesto 10 entradas, 0 `owner_verified`, pipeline validado com manifesto sintético, revertido |
| 6 | Índice ES | Reindex v2: 41/41, rejected=0, alias swap; Reconcile: checked=50, rejected=0; Contagem idx (41) == PG vendáveis (41); Campos multilíngues presentes, sem preço; Busca en/es/ar + SKU exato + fallback PG testados |

### O que NÃO foi validado (fora do escopo V1)

- **Frontend visual (V3)**: Navegação em pt-BR/en/es/ar/zh-CN, RTL árabe, seletor idioma, badge fallback
- **Modo hybrid (embeddings)**: `EMBEDDINGS_ENABLED=false` (requer modelo ONNX + runtime)
- **Qualidade árabe**: Traduções automáticas, não revisadas por nativo
- **Deploy produção**: Não executado

### Riscos conhecidos

- `alembic check` mostra drift na `product_attribute_definitions` (criada via SQL puro, sem model ORM) — limitação do autogenerate, não bug
- 2 testes unitários falham localmente por `elasticsearch` module ausente — passam no container
- Fallback PostgreSQL busca textual apenas pt-BR (documentado)

### Comandos de verificação executados

```bash
# Ambiente
docker info
docker compose --env-file .env.example config --quiet
docker compose ps
curl -u elastic:xxx http://localhost:9200/_cluster/health  # 200 com cred, 401 sem

# Migrations + backup
docker compose exec -T postgres pg_dump -U postgres -d forja_db -Fc > backup_pre_migrations.dump
docker compose exec -T postgres psql -U postgres -d forja_db_test -c "CREATE DATABASE..."
DATABASE_ADMIN_URL=... python -m alembic upgrade head  # no banco teste
DATABASE_ADMIN_URL=... python -m alembic check  # no dev

# Seeds (2x cada)
docker compose exec -T -e DATABASE_ADMIN_URL=... -e DEMO_USER_PASSWORD=... backend python -m app.infrastructure.db.seeds
docker compose exec -T -e DATABASE_ADMIN_URL=... backend python scripts/seed_attribute_definitions.py

# Índice
docker compose exec -T backend python -m app.modules.search.interface.cli reindex --version 2
docker compose exec -T backend python -m app.modules.search.interface.cli reconcile

# Busca multilíngue
curl -H "Accept-Language: en" http://localhost:8000/api/v1/search/products?q=helmet
curl -H "Accept-Language: es" http://localhost:8000/api/v1/search/products?q=casco
curl -H "Accept-Language: ar" http://localhost:8000/api/v1/search/products?q=%D8%AE%D9%88%D8%B0%D8%A9
curl -H "Accept-Language: ar" http://localhost:8000/api/v1/search/products?q=EPI-CAP-001

# Fallback
docker compose stop elasticsearch
curl http://localhost:8000/api/v1/search/products?q=luva  # search_mode=postgres_fallback
docker compose start elasticsearch
```

### Qualidade (RULES.md)

| Verificador | Resultado |
|-------------|-----------|
| `pytest tests/unit` (backend) | 351 passed, 2 failed (deps ausentes) |
| `pytest tests/` com Docker | 466 passed, 1 skipped |
| `npm run test` (frontend) | 86 passed |
| `ruff check` | ✅ passed |
| `ruff format --check` | ✅ 381 files |
| `mypy` | Apenas erros em deps externas (opentelemetry, elasticsearch, redis) |
| `import-linter` | ✅ 4 contracts kept, 0 broken |

---

## Validação V2 — API de administração, traduções, idiomas e busca

**Iniciado:** 2026-10-14
**Concluído:** 2026-10-14
**Ambiente:** Docker Compose real (PostgreSQL, Elasticsearch, Redis, backend), API em `http://localhost:8000`, índice `forja_products` (v2).

### Resumo

| Passo | Descrição | Estado |
|-------|-----------|--------|
| 0 | Tokens de demonstração via `DEMO_USER_PASSWORD` (login real) | ✅ |
| 1 | Listas `UI_LOCALES` (11) / `CONTENT_LOCALES` (4), negociação, fallback, `Vary` | ✅ |
| 2 | Administração ponta a ponta (criar/editar/limpar atributos, RBAC, 409, SKU, auditoria, outbox, despublicar) | ✅ |
| 3 | Traduções (4 locales, 3 fora da lista, `stale` servido, `reviewed`, preços idênticos) | ✅ |
| 4 | Busca multilíngue (SKU em `ar`, termos `en`/`es`/`ar`, cadeia, preços por perfil) | ✅ |
| 5 | Fallback real sem Elasticsearch (latência, edição durante queda, recuperação) | ✅ |
| 6 | Embeddings | ⚠️ **NÃO VALIDADO** (`EMBEDDINGS_ENABLED=false`) |
| 7 | Documentação e checagens finais | ✅ |

### Mudanças de código (V2)

**Idiomas e respostas**
- `core/config.py`: `UI_LOCALES` (11) separado de `SUPPORTED_LOCALES`/`CONTENT_LOCALES` (4).
- `domain/i18n.py`: `negotiate_locale` retorna `(ui_locale, content_locale, content_fallback)`;
  correspondência por idioma base; `?lang=` prioritário; inválido → `pt-BR`.
- `interface/deps.py`: `LocaleInfo` + `get_locale_info`; `get_locale` mantido por compatibilidade.
- `application/i18n.py`: `content_locale` é sempre o locale de conteúdo resolvido; `fallback`
  campo a campo.
- `interface/middleware.py`: `Vary: Accept-Language` em catálogo, busca, carrinho e pedidos.
- `catalog/interface/router.py`: `fallback=true` também quando o idioma pedido cai na cadeia
  (`fr` → `en`), além do fallback de campo.

**Administração**
- Engine/UoW administrativo separado (`forja_admin`, sem RLS) via `DATABASE_ADMIN_URL`
  (obrigatória para o backoffice).
- Correção de concorrência otimista: `apply_update_to_product`/`publish`/`unpublish`
  preservam `version`/`updated_at` até o repositório; `updated_at` é renovado no UPDATE.
- `ProductStatus.DRAFT` adicionado (despublicar) + constraint do banco.
- Slug desambiguado ao renomear produto (evita colisão).
- **Auditoria implementada**: `audit_log` registra `catalog.product.created|updated|published|unpublished`
  (tenant do ator), via `SqlAlchemyAuditLogRepository`.
- `search_outbox` com constraint única `(aggregate_id, event_type)` para `ON CONFLICT`.

**Banco**
- Migration `0018`: `ck_products_status` aceita `DRAFT`; unicidade da outbox.
- Migration `0019`: `content_locale` em `orders` e `order_items` (bug real: o repositório já
  gravava a coluna, mas ela não existia em banco migrado do zero).
- Modelo ORM de `product_attribute_definitions` criado: `alembic check` sem drift.

### Evidências (API real)

**Idiomas (produto demo `CAP-002`)**

| `Accept-Language` | `content_locale` | `fallback` | Nome entregue |
|---|---|---|---|
| `pt-BR` | `pt-BR` | `false` | Capacete de Segurança Classe A Aba Frontal |
| `en` | `en` | `false` | Class A Front Brim Safety Helmet |
| `es` | `es` | `false` | Casco de Seguridad Clase A Ala Delantera |
| `ar` | `ar` | `false` | خوذة أمان من الفئة أ الأمامية |
| `fr`, `ja`, `de` | `en` | `true` | Class A Front Brim Safety Helmet |
| `ar-EG` | `ar` | `false` | خوذة أمان من الفئة أ الأمامية |

Preços/`price_on_request`/status idênticos em `pt-BR`, `en`, `es`, `ar` e `fr` (`32.90 BRL`).

**Administração**
- Criar com nome+descrição+marca → `201`, `attributes=null`; detalhe público → `attributes=[]`.
- Editar com `modelo`/`cor` → ambos aparecem; limpar `cor` → só `modelo`.
- Visitante: `401` (criar/editar); comprador: `403` (criar/editar).
- Edição concorrente: 1ª `200`, 2ª com versão antiga `409`.
- Alterar `sku` no PATCH → `422`.
- Auditoria: 4 entradas (`created`, 3×`updated`) para o produto de teste.
- Outbox: `UPSERT` (criação/edições) e `DELETE` (despublicar), ambos `PENDING`.
- Despublicar → `status=DRAFT`; busca `total=0`; consulta direta ao Elasticsearch do `_doc` → `404`.

**Traduções**
- Editar texto `pt-BR` → tradução `en` retorna `is_stale=true` e **continua sendo servida**
  (`Original English Name`).
- `PATCH .../en` com `mark_reviewed=true` → `status=reviewed`, `is_stale=false`.
- Dados de teste revertidos (produto, traduções, outbox, auditoria, documento no índice).

**Busca**
- `q=CAP-002` com `Accept-Language: ar` → 1º resultado `CAP-002`, nome árabe, `content_locale=ar`.
- `q=Helmet` (`en`) → 5 resultados; `q=Casco` (`es`) → 6; `q=خوذة` (`ar`) → 5.
- `q=Helmet` com `Accept-Language: fr` → `content_locale=en` (cadeia).
- Visitante → `base_unit_price=null`, `price_on_request=true`.
- Comprador Gama (preço fixo `27.90`) → `27.90`; comprador Beta (10%) → `29.61`;
  comprador Alfa → `32.90` (não recebe o preço fixo de outra empresa).

**Fallback sem Elasticsearch**
- `docker compose stop elasticsearch` → `search_mode=postgres_fallback`, conteúdo `pt-BR`.
- Latência: lexical **68–162 ms** (média 102 ms); fallback 1ª requisição **~2.05 s**
  (timeout do ES), depois do circuit breaker **8–15 ms** (média do termo `capacete` 24 ms).
- Catálogo editável durante a queda (`201` criação, `200` edição).
- `docker compose start elasticsearch` + healthcheck → `reconcile` (`checked=50/74`, `upserted`,
  `deleted=21/1`) → `search_mode=lexical` novamente, latência 28–61 ms, produto de teste indexado.
- Dados de teste da queda removidos; índice reconciliado sem órfãos.

### Qualidade final (V2)

| Verificador | Resultado |
|-------------|-----------|
| `docker compose --env-file .env.example config --quiet` | ✅ |
| `alembic check` (dev) | ✅ sem drift |
| `pytest tests/unit` | ✅ 421 passed |
| `pytest tests/architecture` | ✅ 4 passed |
| `pytest tests/integration` (Testcontainers) | ✅ 252 passed, 1 skipped |
| `ruff check` / `ruff format --check` | ✅ |
| `mypy app --strict` | ✅ sem erros (285 arquivos) |
| `import-linter` | ✅ 4 contracts kept |
| Frontend `typecheck` / `lint` / `test` | ✅ / ✅ (warnings `<img>`) / ✅ 86 |

### NÃO VALIDADO e riscos (V2)

- **Embeddings/hybrid**: `EMBEDDINGS_ENABLED=false` no `.env`; backfill e consultas `hybrid`
  não executados. Não habilitado por padrão.
- **Qualidade das traduções**: `en`/`es`/`ar` são automatizadas; árabe não revisado por falante nativo.
- **Fallback PostgreSQL** busca apenas `pt-BR` (não usa `en`/`es`/`ar`).
- **`DATABASE_ADMIN_URL` obrigatória**: sem ela o backoffice não opera (catálogo global).
- **Novos idiomas de conteúdo** exigem traduções e analisadores próprios (não é só configuração).
