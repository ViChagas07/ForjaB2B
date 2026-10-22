# Auditoria de prontidão — Forja B2B

**Data:** 2026-10-22
**Escopo:** auditoria somente de leitura (código, Compose e migrations não foram alterados).
**Snapshot de referência:** HEAD `c3f28da` (`feat(security): adiciona cabecalhos de seguranca e CSP com nonce`).
**Remoto:** `origin/main` em `df34400`.
**Natureza:** projeto de portfólio com dados fictícios; “pronto para produção” não é o objetivo.

> **Nota de concorrência:** durante esta auditoria outro fluxo de trabalho estava alterando
> a árvore (rate limiting em `backend/app/application/rate_limit.py`,
> `backend/app/interface/rate_limit.py` e `backend/app/infrastructure/rate_limit/` ainda
> **não commitados**). No fim da auditoria, `backend/app/main.py` chegou a ficar
> temporariamente com erro de sintaxe na cópia de trabalho (`StaticFiles\nfrom ...`).
> **Nada disso foi commitado nem contado como concluído.** As contagens de teste abaixo
> referem-se ao snapshot `c3f28da` + os testes de CORS já commitados; a suíte completa com
> Docker foi iniciada antes dos 6 testes de security headers.
>
> A versão anterior deste arquivo era uma reconstrução feita no Prompt 09; esta versão
> substitui aquela e cobre os 29 itens do Prompt 01.

## Resumo executivo

- **7 itens EXISTEM**, **16 são PARCIAIS** e **6 são AUSENTES** (de 29).
- A suíte com Docker coletou **704** testes e terminou em **702 passed, 1 failed, 1 skipped**
  (553 s); a falha é o teste de Elasticsearch `test_search_prioriza_sku_exato_e_ignora_acento`,
  por `ConnectionTimeout` no Testcontainers, reproduzível em rerun.
- A suíte sem Docker, já no HEAD `c3f28da`, coletou **710** e terminou em
  **455 passed, 255 skipped** (33,75 s). A diferença de 6 testes é a suíte de security headers.
- **`mypy .` não está verde**: no snapshot havia erros em testes; no HEAD `c3f28da` há
  **1 erro de aplicação** em `backend/app/core/request_context.py:23`, e o WIP de rate limiting
  adiciona mais 2. O CI executa `mypy .`.
- **Rate limiting ainda não está no código commitado** (só configuração e WIP). **Não há
  backup automatizado** (`make db-backup` é documentado, mas o target não existe) e **não há
  limpeza de índices antigos do Elasticsearch**.
- No snapshot, `origin/main` estava **15 commits atrás** do HEAD local; os 15 commits
  locais **não foram enviados**. Após os 3 commits desta auditoria, o total local é 18.
  Outros 14 commits desde a Fase 9A-2 já estavam no remoto.

## 1. Estado real das validações

| Validação | Estado | Evidência |
| :--- | :--- | :--- |
| V1 — ambiente, migrations 0001–0017, seeds, índice v2, busca `en`/`es`/`ar` | **Concluída** (2026-10-14) | Commit `eaba506`; `docs/history/STATUS-log-2026-10.md` §V1; `docs/agent/PROGRESS.md` |
| V2 — admin ponta a ponta, traduções, busca multilíngue, fallback com ES parado, correções | **Concluída** (2026-10-21) | Commit `df34400`; `docs/agent/PROGRESS.md` §V2 |
| V3 — 11 idiomas, RTL, 1037 chaves, capturas visuais | **Concluída** (2026-10-22) | Commits `f7dcc8f`…`7ee3265`; `docs/validation/v3/` (16 JPGs); `docs/I18N.md` |
| Validação Stripe (V4 informal) | **Parcial** | Commits `58c289c`, `535f724`; `docs/STATUS.md` §“Integração Stripe”; checkout test mode, webhook e Playwright 6 passed registrados; **sem cartão real**, sem disputas/chargebacks |
| Suíte completa verde | **Não** | 1 falha reproduzível de infraestrutura de teste (ES/Testcontainers), ver §3 |

**O que ficou pendente:** deploy no Render, teste de carga, rate limiting commitado, backup
restaurável, alertas, OpenAPI exportado, contrato de API e limpeza de índices. Nada disso
foi declarado concluído.

## 2. Commits desde a Fase 9A-2 e estado do remoto

**Base 9A-2:** `6af0986` (mencionado no `PROGRESS.md`).
**Commits no intervalo:** 29. **Já no `origin/main`:** 14. **Locais não enviados:** 15.

Já no remoto (`origin/main` = `df34400`):

```text
9ff34cd fix(config): treat empty Elasticsearch credentials as absent
a1b4bbb fix(catalog): mask price for visitors on the catalog endpoints
073e28d feat: Phase 9A-3a & 9-a — Product photo manifest & attribute model
40b9e9d feat: second setting to the catalogue of the e-commerce
e10c2e7 feat: product management API
7f322a0 feat(frontend): Phase 9-c — Admin product form and public specifications
e0ccd9b feat(frontend): Phase 9-c steps 4-6 — Publication options, customer preview, validation
b60f251 Fase 9B-a Passo 3: Atualiza repositório de pedidos para incluir locale
5d7ecaa Fase 9B-a Passos 4-6: TranslationProvider, admin endpoints, seed demo, docs
c323b49 feat(search): Phase 9B-b - Multilingual search (Elasticsearch)
e0df395 docs: Phase 9B-b - Docker validation complete
64451cc feat(i18n): Validação V3 — 11 UI languages, RTL, fallback badge removal, visual validation prep
eaba506 docs: Validation V1 — environment, migrations, seeds, search index
df34400 feat(catalog): valida V2 (i18n, admin, traducoes e busca) e corrige lacunas
```

Locais, **não enviados** (`origin/main..HEAD`):

```text
f7dcc8f fix(i18n): traduz 1037 chaves e torna paridade obrigatoria
96dd3b4 fix(i18n): move textos fixos do cliente para os dicionarios
33abff3 feat(i18n): seletor nativo com cookie e testes de primeira visita
0397bd6 fix(rtl): classes logicas, icones espelhados e direcao unica
0848b28 fix(i18n): remove selos de fallback e mantem nota so no detalhe
a84a867 fix(cache): inclui o idioma nas chaves de consulta
7ee3265 feat(i18n): valida 11 idiomas no frontend e captura evidencias visuais
6afd5ce docs: reescreve README e organiza documentacao historica
4fa6468 docs: adiciona ADRs, nao-objetivos, changelog e indice
aeb8b6f docs: adiciona relatorio de prontidao e verificacao de links
58c289c feat(payment): integra Stripe Checkout com webhook assinado e CORS
535f724 feat(payment): pix no Stripe, pedido pago, estorno e conciliacao
c74b2c9 fix(db): normaliza URLs libpq em seed e testes de configuracao
d2426b9 feat(security): endurece CORS com origens explicitas
c3f28da feat(security): adiciona cabecalhos de seguranca e CSP com nonce
```

**Conclusão:** não houve push dos 15 commits locais do snapshot (nem dos 3 commits de
documentação desta auditoria). A afirmação “nada foi enviado” é verdadeira para o trabalho
desde `df34400`, mas **não** para todo o intervalo desde 9A-2: 14 commits já estão no
remoto. O `git status` no início da auditoria estava limpo; o WIP de rate limiting apareceu
depois e não faz parte de nenhum commit.

## 3. Contagens reais de testes

### Coleta por diretório (HEAD `c3f28da`)

| Diretório | Testes coletados |
| :--- | ---: |
| `tests/unit` | **449** |
| `tests/integration` | **257** |
| `tests/architecture` | **4** |
| **Total** | **710** |

### Execuções

| Comando | Resultado |
| :--- | :--- |
| `pytest tests/ -q` com Docker (snapshot de 704 testes, antes dos 6 de headers) | **702 passed, 1 failed, 1 skipped** em 553 s |
| `DOCKER_HOST=tcp://127.0.0.1:1 pytest tests/ -q` (HEAD `c3f28da`, 710) | **455 passed, 255 skipped** em 33,75 s |
| `pytest tests/integration/test_search_index_es.py::test_search_prioriza_sku_exato_e_ignora_acento` (rerun) | **1 failed** em 79 s |
| `pytest tests/unit/test_security_headers.py tests/unit/test_cors.py` | **11 passed** |
| `pytest tests/unit tests/architecture` | 453 testes no HEAD (449 + 4) |

**Falha reproduzível:** `test_search_prioriza_sku_exato_e_ignora_acento` falha em
`index.create_versioned_index(version=911)` com
`SearchUnavailableError: search engine unavailable: ConnectionTimeout`; o cliente acessa
`localhost:<porta>` do container ES e o `create_versioned_index` estoura. Não é uma
asserção de domínio: é a fronteira Testcontainers/Elasticsearch. O mesmo teste já havia
sido citado como intermitente no `PROGRESS` (Stripe, 2026-10-22).

### Marcador `integration` está quebrado

`backend/tests/integration/conftest.py:68-71` adiciona `pytest.mark.integration` a **todos**
os itens coletados, não só aos do diretório. Resultado:

- `pytest tests/ -m integration --collect-only` → 710;
- `pytest tests/ -m "not integration"` → **0** (710 deselected).

Ou seja, não é possível selecionar unitários por marcador no CI. O `skip` real sem Docker
vem de `_require_docker()` (`conftest.py:60`), não do marcador. Isso é um bug de metadados,
não de cobertura.

### Comparação com a Fase 9A-2 (508 passed, 1 skipped)

- 508 → 704 no snapshot da suíte Docker = **+196** casos; no HEAD = **+202** (710).
- `git diff 6af0986..HEAD -- backend/tests`: **184 funções `def test_` adicionadas**, **1
  substituída** (`test_card_pagamento_sem_desconto` deu lugar aos testes de cartão/Stripe) e
  **3.381 linhas adicionadas** em 19 arquivos.
- O saldo maior que 184 vem de parametrizações (ex.: locales), casos de integração
  adicionados e novas suítes (i18n, admin, traduções, Stripe, CORS, headers).
- **Não há indício de remoção/ enfraquecimento de testes** para “ficar verde”: a única
  remoção é a substituição coerente com o novo fluxo de cartão.

## 4. Verificação item a item

Legenda: **EXISTE** = implementado e com prova; **PARCIAL** = existe em parte ou sem
garantia; **AUSENTE** = não existe. Esforço: P/M/G. Valor para portfólio: A/M/B.

### Infraestrutura e DevOps

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 1 | CI, Dependabot, CODEOWNERS, template de PR | **PARCIAL** | 3 workflows existem (`ci-backend.yml`, `ci-frontend.yml`, `ci-architecture.yml`). Não há `.github/dependabot.yml`, `CODEOWNERS` nem template de PR. O CI mascara falhas: `bandit ... \|\| true` (`ci-backend.yml:120`), `pip-audit ... \|\| true` (`:124`), `npm audit ... \|\| true` (`ci-frontend.yml:116`), teste frontend `\|\| echo` (`:98`), gitleaks/hadolint `continue-on-error: true` (`ci-architecture.yml:54,68,75,82`). | M | A |
| 2 | Ambientes além do Compose / `render.yaml` | **AUSENTE** | `render.yaml`/`render.yml` não existem; `docker-compose.prod.yml` cobre só o Elasticsearch. `docs/DEPLOY_RENDER.md` diz “NÃO EXECUTADO”. | G | A |
| 3 | Segredos no repositório e histórico; varredura | **PARCIAL** | `.env.example` só tem valores fictícios de dev; `.env` é ignorado. Varredura atual por `sk_test_/sk_live_/whsec_/AKIA/ghp_` → **0** no working tree. Histórico tem 10 `sk_test_` e 19 `whsec_` em `58c289c`/`535f724` (valores dummy de teste/placeholders, um `sk_live_` apenas em comentário do `.env.example`). Gitleaks existe no CI, mas `continue-on-error: true` (`ci-architecture.yml:54`). | M | A |
| 4 | Container: non-root, multi-stage, base, `.dockerignore`, healthcheck, versões | **PARCIAL** | Backend multi-stage (`Dockerfile:7,33`), usuário `forja` (`:67`), `HEALTHCHECK` (`:72`), `tini`; frontend multi-stage e `nextjs` (`frontend/Dockerfile:39,66,70`); `.dockerignore` nos dois. Porém: tags sem digest, contexto de build copia testes, healthcheck usa liveness, e `uvicorn --forwarded-allow-ips "*"` (`Dockerfile:84`) confia em qualquer proxy. | M | M |
| 5 | Backup e restauração testada | **PARCIAL** | Existem 3 dumps não vazios (432 KB, 440 KB, 436 KB) e `pg_dump` no runbook/`PROGRESS`. Mas `docs/RUNBOOK.md:142` manda rodar `make db-backup` e **o target não existe no Makefile**; não há script de restore nem evidência de restauração testada. | M | A |
| 6 | Health checks: liveness, readiness, search | **EXISTE** | `GET /health/live` e alias `/health` (`backend/app/interface/health.py:51,56`); `/health/ready` com probes de PostgreSQL e Redis (`:62`, `app/main.py:545`); `/health/search` separado e sempre 200 (`health.py:75`); Docker healthcheck usa liveness. | — | — |

### Segurança

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 7 | CORS | **EXISTE** | `CORSMiddleware` com origens explícitas, sem `*`, `allow_credentials` configurável e `max_age` (`backend/app/main.py:489-501`); validador rejeita `*`/caminho (`config.py:259-277`); testes `test_cors.py` (5) e chamada real sem `--disable-web-security` registrada no `STATUS` V4. | — | — |
| 8 | Cabeçalhos de segurança no backend e frontend | **EXISTE** | `SecurityHeadersMiddleware` com nosniff, Referrer-Policy, Permissions-Policy, CORP, HSTS condicional e `no-store` em rotas sensíveis (`app/interface/security_headers.py`); CSP com nonce no middleware Next (`frontend/middleware.ts`, `frontend/shared/security/csp.ts`), `X-Frame-Options: DENY` e headers no `next.config.mjs`; 6 testes de headers + 5 de CORS passam. **Não validado em deploy real.** | P | A |
| 9 | Rate limiting (login, busca, admin), Redis, fail-open, XFF | **AUSENTE (WIP)** | No HEAD `c3f28da` só há configuração (`config.py:210-225`) e headers expostos; não há middleware. O WIP não commitado em `backend/app/application/rate_limit.py`, `interface/rate_limit.py` e `infrastructure/rate_limit/` implementa token bucket, store local/Redis e IP via `trusted_proxy_count`, mas **não foi commitado, testado nem contado**. `X-Forwarded-For` só é considerado com `TRUSTED_PROXY_COUNT>0`. | M | A |
| 10 | Varredura de dependências | **PARCIAL** | `pip-audit` e `bandit` (`ci-backend.yml:113-124`) e `npm audit` (`ci-frontend.yml:116`) existem, mas todos com `\|\| true`; nenhuma falha bloqueia o merge. Não há Dependabot. | P | A |
| 11 | Dados pessoais: campos, hash/cifra, rotação do pepper, mascaramento | **PARCIAL** | `email`/`phone` em texto (`models/identity.py:52,54`), CNPJ em texto (`models/companies.py:42`), CPF com HMAC-SHA256 + pepper (`companies/infrastructure/cpf.py:21-22`) e `cpf_encrypted` previsto (`identity.py:56`), mas **nunca preenchido** (só aparece no `NULL` da anonimização). Não há política/teste de rotação do pepper. Logs não incluem PII por convenção, mas não há filtro de redação. | M | A |
| 12 | LGPD: exportação, retificação, exclusão/anonimização | **EXISTE** | `GET /privacy/export`, `PATCH /privacy/me`, `DELETE /privacy/me`, `POST/GET /privacy/consent` (`modules/privacy/interface/router.py:83-130`); anonimização em `privacy/infrastructure/repository.py`; `docs/LGPD.md`. Não há fluxo de operador para terceiros (documentado). | — | — |

### Observabilidade

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 13 | Métricas Prometheus, proteção, alertas, painéis | **PARCIAL** | Métricas de HTTP, pedidos, pagamentos, notificações e busca (`core/metrics.py:14-57`), expostas em `/metrics` **sem autenticação** (`health.py:92-94`). Prometheus scrape config existe, mas não há `rule_files`/Alertmanager; Grafana tem 2 dashboards, porém **não sobe** por datasource default duplicado (`docker/grafana/provisioning/datasources/{datasources,prometheus}.yml`). | M | A |
| 14 | Tracing OpenTelemetry | **EXISTE** | Provider OTLP opcional (`core/telemetry.py:43-70`), FastAPI e SQLAlchemy instrumentados (`:78-87`), endpoint configurável (`config.py:94-96`); sem spans de negócio manuais. | P | M |
| 15 | Logs: formato, redação, correlação | **PARCIAL** | JSON + `request_id` + `trace_id` (`core/logging.py:24-29,39`), erros RFC 7807 sem stack (`interface/errors.py`). **Não há processador de redação** de PII; a ausência de PII depende de disciplina dos chamadores. | P | A |
| 16 | Sentry ou similar | **AUSENTE** | Nenhuma dependência/configuração de Sentry, Rollbar ou equivalente no backend/frontend. | P | B |

### Dados e migrations

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 17 | Migrations: downgrade/upgrade, `alembic check`, idempotência | **PARCIAL** | 20 revisions e 20 `downgrade()`; `test_alembic_env` faz `upgrade head`; `test_persistence_schema` roda `command.check` (`tests/integration/test_persistence_schema.py:231-240`); `make migration-rollback` existe. **Não há teste/CI de downgrade**; `alembic check` só roda dentro da suíte de integração. | P | A |
| 18 | Reconciliação do índice: agendamento, exclusão mútua, métrica de sucesso | **PARCIAL** | Beat agenda `dispatch-search-outbox` a cada 15 s e `reconcile-search-index` a cada 900 s (`tasks/celery_app.py:34-40`); CLI `reconcile` existe. **Sem lock/mutex** entre execuções e **sem métrica de última execução bem-sucedida**; o beat local está em restart por permissão (`celerybeat-schedule`). | M | A |
| 19 | Outbox: limite de tentativas, estado final, reprocessamento | **PARCIAL** | `attempts`, `last_error` e status `PENDING/PROCESSED/FAILED/DEAD_LETTERED` (`models/search.py:37-57`); `list_due` só pega `FAILED` com `attempts < max` (`outbox_repository.py:17-20`); `mark_failed` increments (`:26-31`). **Nunca grava `DEAD_LETTERED`**: ao atingir o limite, o evento fica `FAILED` e para de ser selecionado. Não há CLI de reprocessamento nem métrica de idade/lag. | M | A |
| 20 | Limpeza de versões antigas do índice | **AUSENTE** | `swap_alias` remove o alias de todos e aponta para o novo (`elasticsearch.py:361-369`), mas não apaga o índice anterior; o CLI só tem `bootstrap`, `reindex`, `reconcile`, `backfill-embeddings` (`cli.py:49-63`). | P | M |

### API

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 21 | OpenAPI: geração, exportação, versionamento, publicação; erro padrão | **PARCIAL** | OpenAPI gerado em runtime (`main.py:259`) e Swagger em `/docs`; erros RFC 7807 padronizados (`interface/errors.py`). **Não há exportação** (`openapi.json` versionado), geração de tipos nem publicação; em produção `/docs` e `/openapi.json` são desligados. | M | A |
| 22 | Versionamento e depreciação (`/v1`, `Deprecation`/`Sunset`) | **PARCIAL** | Prefixo `/api/v1` em `app/interface/v1/router.py`; não há política de depreciação, headers `Deprecation`/`Sunset` nem versão v2. | P | B |
| 23 | Idempotência em pedido, checkout, pagamento, produto | **PARCIAL** | `idempotency_key` no **corpo** de pedido (`ordering/interface/schemas.py:26`) e pagamento (`payment/interface/schemas.py:29`), com unique parcial e conflito 409; crédito também. **Não há header `Idempotency-Key`**, middleware genérico nem idempotência na criação de produto admin. | M | A |
| 24 | Webhooks: assinatura, tolerância, replay, idempotência | **EXISTE (legado parcial)** | Stripe: `Stripe-Signature` via `stripe.Webhook.construct_event` (`payment/interface/router.py:196`; tolerância padrão do SDK, 300 s), evento idempotente por `(provider,event_id)`. Webhook legado `/payments/webhook`: HMAC-SHA256 do corpo (`:99-104,224-235`), **sem timestamp/tolerância**, mas idempotente por `event_id`; replay depende da constraint do evento. | — | — |

### Testes

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 25 | Integração de API (auth, RBAC/RLS, catálogo/admin, busca, traduções, carrinho, pedido) | **EXISTE** | 257 testes em `tests/integration/`, incluindo `test_auth_api`, `test_rls_isolation`, `test_persistence_rls`, `test_catalog_api`, `test_search_api`, `test_ordering_api`, `test_payment_api`, `test_privacy_api`. **Marcador `integration` quebrado** (marca todos; ver §3) e 1 falha de ES no full run. | — | — |
| 26 | Testes de contrato (tipos gerados do OpenAPI, drift) | **AUSENTE** | Sem `openapi-typescript`/gerador; `frontend/core/domain` e schemas Zod são escritos à mão. Testes de API do frontend mockam HTTP, não verificam o OpenAPI. | M | M |
| 27 | Testes de carga (k6 etc.) | **AUSENTE** | Nenhum k6/Locust/Gatling; `docs/testing/LOAD.md` declara “NÃO EXECUTADO”. Só há medições pontuais de busca na V2, que não são carga. | G | A |
| 28 | Simulações de falha (ES, Redis, PostgreSQL) | **PARCIAL** | Testes unitários de fallback/breaker/timeouts (`test_search_timeouts.py`, `test_search_usecases.py`); runbook com ES parado e breaker; V2 executou ES parado manualmente. **Não há teste automatizado** de Redis fora, PostgreSQL fora, nem injeção de falha no CI. | M | A |

### Documentação

| # | Item | Status | Prova | Esf. | Valor |
| :-: | :--- | :--- | :--- | :-: | :-: |
| 29 | README, diagramas, ADRs, runbooks, SECURITY, CHANGELOG, licença | **PARCIAL** | README com diagramas Mermaid e validação; 13 ADRs; `docs/SEARCH/RUNBOOK`, `docs/RUNBOOK`, `docs/SECURITY`, `CHANGELOG`, `docs/INDEX`. **Sem `LICENSE`**; README e `FINAL_REPORT` estão **desatualizados** sobre CORS e pagamento (dizem “CORS ausente”/“fake”), e o `GAP_AUDIT` anterior era uma reconstrução. | P | A |

## 5. Correções às afirmações anteriores

| Afirmação anterior | Realidade verificada |
| :--- | :--- |
| “CORS ausente” (README, `FINAL_REPORT`, GAP_AUDIT do Prompt 09) | **Falso agora.** CORS explícito implementado em `58c289c`/`d2426b9` (`main.py:489-501`), com testes; a validação visual V3 foi refeita sem `--disable-web-security` (registro no `STATUS`). |
| “Pagamento fake, sem integração real” | **Parcialmente falso.** Há Stripe Checkout em **test mode** (cartão/PIX), webhook assinado, estorno e conciliação; Boleto continua interno. Não há pagamento live, adquirente de produção, disputas/chargebacks. A frase “fake” ficou restrita ao gateway local e ao Boleto. |
| “677 testes com Docker” (relatório anterior) | **Desatualizado.** No snapshot auditado: 704 coletados, **702 passed/1 failed/1 skipped**; no HEAD `c3f28da`: 710 coletados (449/257/4). O aumento vem de i18n, admin, traduções, Stripe, CORS e headers — não de remoção de testes. |
| “`mypy app --strict` 0 erros” | **Falso no HEAD `c3f28da`.** Há 1 erro em `backend/app/core/request_context.py:23`; o WIP de rate limiting adiciona 2. `mypy .` segue com erros em testes. |
| “Rate limiting não implementado” | **Verdadeiro no HEAD committed.** Há só configuração; o WIP não commitado já tem token bucket/Redis/local, mas não deve ser contado. |
| “Outbox tem limite e estado final” | **Parcial.** O limite existe, mas `DEAD_LETTERED` nunca é gravado; após `max_attempts`, o evento fica `FAILED` e para de ser selecionado. |
| “Backup documentado” | **Parcial.** Há dumps e texto, mas `make db-backup` **não existe** no Makefile; restauração nunca foi testada. |
| “Observabilidade com Grafana” | **Parcial.** OTel/Prometheus existem; Grafana não sobe (dois datasources default) e não há alertas. |
| “Nenhum push” | **Nuance.** Os 15 commits locais não foram enviados; porém 14 commits desde 9A-2 já estão em `origin/main` (`df34400`). O remoto não tem o trabalho de i18n final, docs, Stripe e security. |
| “Suíte padrão sem Docker termina sem erros” | **Verdadeiro** para a execução de 710: 455 passed, 255 skipped, 0 failed. Mas o marcador `integration` não seleciona corretamente (marca todos). |

## 6. Backlog priorizado

Ordem sugerida; o prompt é uma proposta de divisão, não uma ordem rígida.

| Prioridade | Item | Prompt sugerido |
| :---: | :--- | :--- |
| **P0** | Corrigir a falha reproduzível do teste de ES/Testcontainers (ou isolar/ajustar timeout e documentar) | 06 |
| **P0** | Corrigir `mypy app` (`request_context.py:23`) e `mypy .`; fazer o CI falhar de verdade | 02 |
| **P0** | Remover `\|\| true`/`continue-on-error` e o `\|\| echo` do teste frontend; tornar audit/gitleaks/hadolint bloqueantes | 02 |
| **P0** | Implementar/commitar rate limiting com testes, fail-open e XFF confiável (WIP atual) | 03 |
| **P0** | Criar `make db-backup`/script de restore e testar uma restauração | 05 |
| **P1** | Atualizar README/FINAL_REPORT para CORS, Stripe, headers e contagens reais | 09 |
| **P1** | `render.yaml`/Environment Groups, deploy real, healthchecks e CORS/Stripe no Render | 07 |
| **P1** | Alertas Prometheus, proteção de `/metrics`, Sentry e dashboards válidos | 04 |
| **P1** | Outbox: gravar `DEAD_LETTERED`, CLI de reprocessamento, métrica de lag; lock no reconcile | 05 |
| **P1** | Limpeza de índices antigos do Elasticsearch e retenção | 05 |
| **P1** | Corrigir marcador `integration` e adicionar E2E/format/depcruise ao CI | 06 |
| **P1** | Exportar OpenAPI versionado e gerar tipos/contract check do frontend | 08/06 |
| **P2** | Aceitar `Idempotency-Key` no header e idempotência na criação de produto | 08 |
| **P2** | Política de rotação do pepper e criptografia de CPF (`cpf_encrypted`) | 03 |
| **P2** | Webhook legado com timestamp/tolerância (ou removê-lo) | 08 |
| **P2** | Testes de carga com k6 e SLOs | 06 |
| **P2** | Política de depreciação (`Deprecation`/`Sunset`) | 08 |
| **P2** | Licença e decisão sobre `.commandcode/` | 09 |

## 7. Fora de escopo para um projeto de portfólio

- **WAF próprio / SOC 2 / ISO 27001:** são programas organizacionais, não features de
  portfólio; o custo não se justifica sem operação real.
- **Vault/AWS Secrets Manager:** um `.env` local + Environment Groups no deploy bastam
  para demonstrar a prática; o gerenciador dedicado é decisão de produção.
- **Distroless/Chainguard:** as imagens atuais já são non-root e multi-stage; endurecer
  mais não muda a narrativa do projeto.
- **Chaos engineering completo:** as simulações pontuais (ES parado, breaker, reindex)
  cobrem o argumento; falta ambiente estável e SLOs para experimentos formais.
- **Pact/consumer-driven contracts:** não há consumidores independentes; o custo de um
  broker não se paga.
- **Feature flags e testes A/B:** sem tráfego real, não há hipótese estatística; flags
  apenas adicionariam dívida.
- **Réplicas de leitura/CDN/ILM:** o volume e o tráfego de demonstração não justificam;
  ficam como evolução documentada, não como pendência de portfólio.
- **Pagamento live / PCI:** exige adquirente, compliance e operação; o Stripe test mode
  demonstra o fluxo sem prometer produção.
- **Tradução nativa dos 11 idiomas / admin multilíngue:** a revisão nativa é trabalho
  humano externo; o admin em pt-BR é decisão de escopo.

## 8. Limitações desta auditoria

- O repositório estava sendo alterado durante a auditoria; a árvore de trabalho chegou a
  ficar inválida (`main.py` com `\n` literal). As contagens e status referem-se ao snapshot
  `c3f28da` e ao WIP explicitamente marcado; uma reauditoria após o commit do rate limiting
  é necessária.
- Não foi possível consultar os runs do GitHub (sem `gh`/API autenticada); “CI” foi
  verificado por arquivos, não por status de execução.
- `gitleaks` não está instalado localmente; a varredura de segredos foi por regex e pelo
  job (não bloqueante) do CI.
- Não houve teste de restauração de backup, carga, deploy ou chaos; tudo isso está marcado
  como NÃO VALIDADO.
- As conclusões sobre “produção” são de portfólio: não há SLO, capacity planning nem
  operação real.
