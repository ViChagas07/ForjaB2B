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
| 4 | Busca lexical e fallback (Postgres) | ⏳ |
| 5 | Busca semântica (PGVector) e fusão por RRF | ⏳ |
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

## Próximos passos sugeridos

1. Rotação do segredo Google (responsável).
2. Normalizar `.env` local e re-inicializar roles para exercitar `make migrate` +
   fluxo de notificação com Mailpit (`:8025`).
3. Implementar as funcionalidades fora do escopo (busca, RFQ, catálogo-escrita,
   DANFE/XML etc.) em fases futuras. A busca tem plano próprio em
   `docs/search/PLAN.md` (Fases 2–6, a partir da Fase 2: Elasticsearch e cliente).
4. Integração com o frontend (fases futuras).
