# Índice da documentação

Mapa dos documentos por tema. “Atual” = descreve o estado de 2026-10-22; “histórico” =
preservado, congelado e possivelmente superado. O README da raiz é a porta de entrada.

## Comece aqui

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`README.md`](../README.md) | Visão geral, arquitetura, funcionalidades, execução local, validação e limitações | Atual |
| [`docs/STATUS.md`](STATUS.md) | Retrato único do que existe e do que falta | Atual |
| [`docs/readiness/FINAL_REPORT.md`](readiness/FINAL_REPORT.md) | Auditoria inicial → estado atual, contagens, pendências e riscos | Atual |
| [`docs/readiness/GAP_AUDIT.md`](readiness/GAP_AUDIT.md) | Checklist de lacunas observado antes desta entrega (com nota de proveniência) | Atual |
| [`docs/NON_GOALS.md`](NON_GOALS.md) | O que não foi adotado, o que foi feito no lugar e o que seria feito em produção | Atual |
| [`CHANGELOG.md`](../CHANGELOG.md) | Marcos por data do histórico Git | Atual |

## Arquitetura e decisões

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | Clean Architecture, bounded contexts, RLS, busca, preços, i18n | Atual |
| [`docs/ADRs/`](ADRs/) | 13 ADRs (0001–0013) | Atual |
| [`docs/ADRs/0004-busca-hibrida.md`](ADRs/0004-busca-hibrida.md) | Busca lexical + fallback + semântica opcional com RRF | Atual |
| [`docs/ADRs/0005-postgresql-fonte-de-verdade-rls.md`](ADRs/0005-postgresql-fonte-de-verdade-rls.md) | PostgreSQL como fonte de verdade e RLS multi-tenant | Atual |
| [`docs/ADRs/0006-precos-fora-do-indice.md`](ADRs/0006-precos-fora-do-indice.md) | Preço fora do índice e preço consultivo | Atual |
| [`docs/ADRs/0007-traducoes-armazenadas.md`](ADRs/0007-traducoes-armazenadas.md) | Traduções armazenadas e fallback de idioma | Atual |
| [`docs/ADRs/0008-atributos-jsonb.md`](ADRs/0008-atributos-jsonb.md) | Atributos JSONB e definições por categoria | Atual |
| [`docs/ADRs/0009-outbox-indice-versionado.md`](ADRs/0009-outbox-indice-versionado.md) | Outbox, reconciliação e alias | Atual |
| [`docs/ADRs/0010-rate-limiting-redis.md`](ADRs/0010-rate-limiting-redis.md) | Rate limiting proposto (não implementado) | Atual / lacuna |
| [`docs/ADRs/0011-idempotencia.md`](ADRs/0011-idempotencia.md) | Idempotência no corpo, não no header | Atual |
| [`docs/ADRs/0012-timeouts-circuit-breaker.md`](ADRs/0012-timeouts-circuit-breaker.md) | Timeouts e circuit breaker | Atual |
| [`docs/ADRs/0013-observabilidade-segredos.md`](ADRs/0013-observabilidade-segredos.md) | Observabilidade proporcional e segredos | Atual / parcial |

## Busca

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/search/RUNBOOK.md`](search/RUNBOOK.md) | Operação, índice, fallback, deploy, métricas e limitações | Atual |
| [`docs/search/PLAN.md`](search/PLAN.md) | Plano original das Fases 1–6 (ES 8.15, antes da implementação) | Histórico (com nota) |
| [`docs/ADRs/0004-busca-hibrida.md`](ADRs/0004-busca-hibrida.md) | Decisão de busca e estado real | Atual |
| [`docs/ADRs/0009-outbox-indice-versionado.md`](ADRs/0009-outbox-indice-versionado.md) | Sincronização e alias | Atual |
| [`docs/ADRs/0012-timeouts-circuit-breaker.md`](ADRs/0012-timeouts-circuit-breaker.md) | Degradação e breaker | Atual |

## Segurança e privacidade

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/SECURITY.md`](SECURITY.md) | Credenciais, RBAC, RLS, OAuth, webhook, exposição | Atual |
| [`docs/LGPD.md`](LGPD.md) | Direitos, anonimização, auditoria e limitações | Atual |
| [`docs/ADRs/0001-payment-webhook-hmac.md`](ADRs/0001-payment-webhook-hmac.md) | Webhook HMAC | Atual |
| [`docs/ADRs/0003-lgpd-deletion-anonymization.md`](ADRs/0003-lgpd-deletion-anonymization.md) | Exclusão como anonimização | Atual |
| [`docs/ADRs/0005-postgresql-fonte-de-verdade-rls.md`](ADRs/0005-postgresql-fonte-de-verdade-rls.md) | RLS | Atual |
| [`docs/ADRs/0010-rate-limiting-redis.md`](ADRs/0010-rate-limiting-redis.md) | Rate limiting (proposto) | Lacuna |
| [`docs/ADRs/0013-observabilidade-segredos.md`](ADRs/0013-observabilidade-segredos.md) | Segredos e observabilidade | Parcial |

## Dados e catálogo

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/CATALOG_ADMIN.md`](CATALOG_ADMIN.md) | Modelo de atributos, admin, validação e formulário | Atual |
| [`docs/CATALOG_DEMO.md`](CATALOG_DEMO.md) | Fotos, manifesto, licença e checklist do responsável | Atual |
| [`docs/ADRs/0006-precos-fora-do-indice.md`](ADRs/0006-precos-fora-do-indice.md) | Preços por empresa | Atual |
| [`docs/ADRs/0008-atributos-jsonb.md`](ADRs/0008-atributos-jsonb.md) | Atributos | Atual |
| [`docs/ADRs/0009-outbox-indice-versionado.md`](ADRs/0009-outbox-indice-versionado.md) | Outbox/índice | Atual |

## API

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/API.md`](API.md) | Mapa de endpoints, auth, erros, paginação e CORS | Atual |
| `http://localhost:8000/docs` | Swagger UI em runtime (fora de produção) | Execução local |
| `http://localhost:8000/openapi.json` | OpenAPI em runtime (fora de produção) | Execução local |

## Testes e validação

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/testing/LOAD.md`](testing/LOAD.md) | Estado (não executado) e roteiro de carga | Atual / lacuna |
| [`docs/readiness/FINAL_REPORT.md`](readiness/FINAL_REPORT.md) | Contagens, evidências, falhas e riscos | Atual |
| [`docs/agent/PROGRESS.md`](agent/PROGRESS.md) | Log cronológico das sessões e validações V1/V2/V3 | Histórico (com nota) |
| [`docs/validation/v3/`](validation/v3/) | 16 capturas reais de i18n/RTL | Evidência |

## i18n

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/I18N.md`](I18N.md) | 11 idiomas de UI, 4 de conteúdo, fallback, admin e busca | Atual |
| [`docs/ADRs/0007-traducoes-armazenadas.md`](ADRs/0007-traducoes-armazenadas.md) | Decisão de traduções armazenadas | Atual |
| [`frontend/i18n/locales.ts`](../frontend/i18n/locales.ts) | Lista única de locales e RTL | Código |
| [`frontend/messages/`](../frontend/messages/) | 11 dicionários | Código |

## Deploy e operação

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/DEPLOY_RENDER.md`](DEPLOY_RENDER.md) | Roteiro e pendências de deploy no Render (não executado) | Atual / lacuna |
| [`docs/RUNBOOK.md`](RUNBOOK.md) | Operação local, troubleshooting, backup e métricas | Atual |
| [`docs/search/RUNBOOK.md`](search/RUNBOOK.md) | Operação da busca e do índice | Atual |
| [`docker-compose.yml`](../docker-compose.yml) | Stack de desenvolvimento | Código |
| [`docker-compose.prod.yml`](../docker-compose.prod.yml) | Override de ES para VPS | Código |

## Agentes e processo

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/agent/RULES.md`](agent/RULES.md) | Regras de trabalho, limites e checagens | Processo |
| [`docs/agent/PROGRESS.md`](agent/PROGRESS.md) | Log de sessões e validações | Histórico (com nota) |

## Histórico

| Documento | Conteúdo | Estado |
| :--- | :--- | :--- |
| [`docs/history/STATUS-log-2026-10.md`](history/STATUS-log-2026-10.md) | Log antigo do STATUS (fases iniciais até V3) | Histórico |
| [`docs/history/README-pt-BR-legacy.md`](history/README-pt-BR-legacy.md) | README antigo de backend | Histórico |
| [`docs/history/phase9bc-snapshot.md`](history/phase9bc-snapshot.md) | Snapshot da Fase 9B-c | Histórico |
| [`docs/history/v3-status-snapshot.md`](history/v3-status-snapshot.md) | Snapshot intermediário da V3 | Histórico |

## Verificação de links

```bash
python scripts/check_markdown_links.py
```

O script ignora links externos e âncoras e, por padrão, não audita `docs/history/` nem o log
`docs/agent/PROGRESS.md` (documentos congelados). Use `--include-history` para incluí-los.
