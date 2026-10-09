# Forja B2B — Status do Backend

> Última atualização: 2026-10-09. Este documento é a fonte de verdade do estado
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
| `pytest tests/` | **355 passed** (unidade + integração com Testcontainers) |
| `ruff check .` | ✅ sem erros |
| `ruff format --check .` | ✅ 301 arquivos formatados |
| `mypy .` (strict) | ✅ 291 arquivos sem erros |
| `import-linter` | ✅ 4 contratos mantidos, 0 quebrados |
| `docker compose config --quiet` | ✅ válido |
| Alembic (drift) | ✅ coberto por `test_persistence_migrations.py` |

> Nota de ambiente: a validação foi executada com as variáveis de
> docker-compose **removidas** do ambiente do processo (o `.env`/ambiente local
> injeta `DATABASE_URL=...@postgres:5432`, o que faria `test_defaults_de_desenvolvimento`
> falhar por sobrescrever o default). O comando exato de execução limpa está em
> `docs/RUNBOOK.md`.

## Limitações e pendências (sem ocultar)

- **Rotação do segredo Google exposto**: pendente do responsável no Google Cloud.
  NÃO foi realizada nesta entrega.
- **ETAPA 13 — observabilidade**: a fundação de OTel/logging/health já existia e
  foi preservada; não foram adicionados dashboards Grafana novos nem métricas
  Prometheus customizadas por fluxo (item 13.1 parcial). Documentado como
  pendência.
- **Celery/RabbitMQ em produção**: o despacho da outbox depende do `celery-beat`
  (adicionado ao compose) + `celery-worker`; ambos foram validados por import
  de módulo, mas o fluxo ponta a ponta com broker real não foi exercitado nesta
  máquina (ver "Validação via Docker").
- **Integração ponta a ponta** (frontend ↔ backend): fora do escopo desta entrega
  (backend-only); o backend está pronto para consumo.

## Próximos passos sugeridos

1. Rotação do segredo Google (responsável).
2. Exercitar o fluxo de notificações com `docker compose up` (Mailpit em `:8025`).
3. Adicionar métricas Prometheus/dashboards por fluxo crítico (13.1 completo).
4. Integração com o frontend (fases futuras).
