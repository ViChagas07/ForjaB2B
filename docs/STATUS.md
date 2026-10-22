# Forja B2B — estado atual

> **Última atualização:** 2026-10-22
> **Base:** commit `7ee3265` (branch `main`, 7 commits à frente de `origin/main`) + esta
> entrega de documentação.
> **Natureza:** projeto de portfólio. Dados, marcas, CNPJs, preços e CA são fictícios.
> O estado consolidado de prontidão está em
> [`docs/readiness/FINAL_REPORT.md`](readiness/FINAL_REPORT.md). O histórico completo
> (log antigo) está em [`docs/history/STATUS-log-2026-10.md`](history/STATUS-log-2026-10.md).

## O que existe

| Área | Estado | Evidência principal |
| :--- | :--- | :--- |
| Identidade, JWT, refresh, RBAC, OAuth Google opcional | Implementado | `backend/app/modules/identity`, `backend/app/application/security.py` |
| Empresas/CNPJ, aprovação, membros por papel | Implementado | `backend/app/modules/companies` |
| Catálogo global, categorias, marcas, imagens, atributos JSONB | Implementado | `backend/app/modules/catalog`, migration `0017` |
| Preço por empresa (negociado/desconto/lista) e consultivo | Implementado | `backend/app/domain/pricing.py`, migration `0014` |
| Carrinho, pedido, crédito, faturamento, frete, impostos | Implementado | `backend/app/modules/{cart,ordering,credit,invoicing,shipping,tax}` |
| Pagamento fake (PIX/cartão/boleto) + webhook HMAC | Implementado (fake) | `backend/app/modules/payment/infrastructure/gateway.py` |
| Notificações outbox + Celery/RabbitMQ + Mailpit | Implementado | `backend/app/modules/notification`, `app/tasks` |
| LGPD (exportação, retificação, anonimização, consentimento) | Implementado | `backend/app/modules/privacy`, `docs/LGPD.md` |
| Busca lexical ES + fallback PostgreSQL | Implementado e validado | `backend/app/modules/search`, `docs/search/RUNBOOK.md` |
| Busca semântica pgvector + RRF | Implementado, **desligado por padrão** | `EMBEDDINGS_ENABLED=false`, ADR-0004 |
| Busca multilíngue (en/es/ar) e 4 locales de conteúdo | Implementado | `docs/I18N.md`, migration `0016` |
| Interface em 11 idiomas, RTL árabe | Implementado | `frontend/i18n/locales.ts`, `frontend/messages/*.json` |
| Admin de catálogo (CRUD/publicação/atributos/traduções) | Implementado | `backend/app/modules/catalog/interface/admin_router.py`, frontend admin |
| Observabilidade (OTel/Prometheus/Grafana, logs JSON, health) | Parcial | `backend/app/core/telemetry.py`, `docker/`; Grafana local falha |
| CI (backend/frontend/arquitetura) | Workflows existem; status não verificado | `.github/workflows/` |
| Rate limiting | **Não implementado** | ADR-0010 (proposto); Redis sem limitador |
| Deploy em provedor | **Não executado** | `docs/DEPLOY_RENDER.md` |
| Teste de carga | **Não executado** | `docs/testing/LOAD.md` |
| Licença | **Não definida** | não há `LICENSE` |

## Validação executada em 2026-10-22

| Verificação | Resultado |
| :--- | :--- |
| `pytest tests/unit tests/architecture` | **425 passed** |
| `pytest tests/` sem Docker | **427 passed, 251 skipped** |
| `pytest tests/` (Docker/Testcontainers) | **677 passed, 1 skipped** |
| `ruff check .` / `ruff format --check .` | OK / **384 files already formatted** |
| `mypy app --strict` | **285 files, 0 errors** |
| `mypy .` (o que o CI roda) | **48 errors em 5 arquivos de teste** |
| `lint-imports --config .import-linter` | **4/4 contratos** |
| `npm run typecheck` / `npm run lint` | OK / OK (3 warnings `<img>`) |
| `npm run test` (frontend) | **102 passed** |
| `npm run build` (frontend) | OK |
| `docker compose --env-file .env.example config --quiet` | OK |
| `docker compose ps` | 9 healthy; `forja-grafana` e `forja-celery-beat` em restart; frontend criado, não iniciado |

## Busca — estado real

- **Padrão:** `lexical` no Elasticsearch com **fallback PostgreSQL**; `search_mode` é
  sempre informado.
- **Índice:** `forja_products_vN` + alias; mapping atual v2; ES 9.5.5 / cliente 9.5.1.
- **Timeouts:** 2 s e 0 retries na busca; 30 s/3 na indexação; breaker 3 falhas/15 s.
- **Fallback:** `tsvector('portuguese')` + `unaccent` + `pg_trgm`; busca apenas `pt-BR`.
- **Semântica:** `EMBEDDINGS_ENABLED=false`; RRF implementado e validado localmente na
  Fase 7, não no estado padrão nem em produção.
- **Evidência V2 (sessão anterior):** termos `en`/`es`/`ar`, SKU exato, preço consultivo,
  preço por empresa, ES parado → `postgres_fallback`, recuperação e reconciliação. Ver
  `docs/agent/PROGRESS.md`.
- **Não reexecutado em 2026-10-22.**

## i18n — estado real

- 11 idiomas de interface; 4 de conteúdo (`pt-BR`, `en`, `es`, `ar`).
- 337 chaves por dicionário; 1.037 chaves traduzidas no Passo 1 da V3; teste de paridade
  obrigatório.
- Árabe é o único RTL (`rtlLocales = ["ar"]`); fontes Noto Sans/CJK/árabe.
- **Não revisado por falante nativo**, especialmente árabe.
- 16 capturas em `docs/validation/v3/`; spec Playwright com 5 passed registrado no
  `PROGRESS`; não reexecutado nesta sessão.

## Segurança e privacidade

- RLS `FORCE` por `company_id`; tenant do JWT; roles `forja_app`/`forja_admin` sem
  `BYPASSRLS`.
- JWT curto + refresh com rotação; Argon2id; OAuth com `state` e exchange code de uso
  único.
- Webhook HMAC-SHA256 sobre o corpo bruto.
- Sem segredo real versionado; `.env.example` só com valores fictícios.
- LGPD self-service; anonimização preserva registros financeiros/fiscais/auditoria.
- **Lacunas:** sem rate limiting, sem WAF, sem secret manager; CORS ausente.

## Limitações e pendências (não ocultar)

1. **CORS ausente** no backend; frontend não funciona em navegador comum sem proxy/CORS.
2. **`mypy .` falha** em 48 erros de testes; o CI roda `mypy .`.
3. **Grafana** reinicia por datasource default duplicado; **celery-beat** reinicia por
   permissão em `celerybeat-schedule`.
4. **Rate limiting não implementado**; ADR-0010 é proposta.
5. **Idempotência no corpo** (`idempotency_key`), não no header `Idempotency-Key`.
6. **Embeddings desligados**; `hybrid` não é padrão; fallback PG só `pt-BR`.
7. **Traduções não revisadas por nativos**; árabe é demonstração.
8. **Pagamento fake**, sem adquirente real.
9. **Deploy e carga não executados**; sem URL pública nem números de produção.
10. **Licença ausente**; todos os direitos reservados por padrão.
11. **3 produtos do seed** com descrição nula (`EPI-LUV-002`, `EPI-RES-003`,
    `MAQ-PAR-004`).
12. **`.commandcode/` versionado** (arquivos de ferramentas do agente); decisão do
    responsável.

## Próximos passos

1. Corrigir `mypy .` (ou ajustar o CI para `mypy app --strict` com justificativa) e
   verificar os runs da CI.
2. Resolver CORS/proxy e validar o frontend em navegador comum.
3. Corrigir Grafana e celery-beat; reexecutar `reconcile`.
4. Implementar rate limiting (ADR-0010) ou declarar explicitamente que o WAF cobre.
5. Definir licença, tirar capturas adicionais se necessário e revisar traduções.
6. Executar deploy e teste de carga em staging; só então atualizar este documento.
