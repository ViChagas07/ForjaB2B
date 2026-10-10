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
| 2 | Elasticsearch e cliente (ES 9.5.5 + `elasticsearch-py` 9.5.1) | ⏳ |
| 3 | Índice e sincronização (outbox + reconciliação) | ⏳ |
| 4 | Busca lexical e fallback (Postgres) | ⏳ |
| 5 | Busca semântica (PGVector) e fusão por RRF | ⏳ |
| 6 | Produção, documentação e fechamento | ⏳ |

- **Fase 1 (2026-10-10):** auditoria somente-leitura e plano completo em `docs/search/PLAN.md`.
  Nenhum código/Compose/migration alterado.
- **Achado da auditoria:** o módulo `search` é scaffold vazio; o Elasticsearch 8.15.0 está
  **provisionado no Compose mas não integrado** (o backend ignora `ELASTICSEARCH_*`); não há
  pgvector nem embeddings; o catálogo é global e somente leitura em runtime (sem caminho de
  escrita de produto), então a frescura do índice dependerá de **reindex + reconciliação**.

## Próximos passos sugeridos

1. Rotação do segredo Google (responsável).
2. Normalizar `.env` local e re-inicializar roles para exercitar `make migrate` +
   fluxo de notificação com Mailpit (`:8025`).
3. Implementar as funcionalidades fora do escopo (busca, RFQ, catálogo-escrita,
   DANFE/XML etc.) em fases futuras. A busca tem plano próprio em
   `docs/search/PLAN.md` (Fases 2–6, a partir da Fase 2: Elasticsearch e cliente).
4. Integração com o frontend (fases futuras).
