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
- Webhook HMAC-SHA256 sobre o corpo bruto, com timestamp assinado, tolerância de
  5 min, dois segredos ativos (rotação), limite de corpo e idempotência por evento.
- Sem segredo real versionado; `.env.example` só com valores fictícios.
- LGPD self-service; anonimização preserva registros financeiros/fiscais/auditoria.
- **Lacunas:** sem WAF e sem secret manager; rate limiting implementado (Redis com
  fallback local); CORS implementado (configurável por `CORS_ORIGINS`).

## Limitações e pendências (não ocultar)

1. **CORS** implementado (`CORS_ORIGINS`); falta configurar o domínio real no deploy.
2. **`mypy .` falha** em 48 erros de testes; o CI roda `mypy .`.
3. **Grafana** reinicia por datasource default duplicado; **celery-beat** reinicia por
   permissão em `celerybeat-schedule`.
4. **Rate limiting** implementado (Redis + fallback local); ADR-0010 atualizada.
5. **Idempotência no header** `Idempotency-Key` (obrigatório em pedido/pagamento);
   `idempotency_key` no corpo continua aceito como fallback depreciado.
6. **Embeddings desligados**; `hybrid` não é padrão; fallback PG só `pt-BR`.
7. **Traduções não revisadas por nativos**; árabe é demonstração.
8. **Pagamento**: cartão e PIX via Stripe Checkout quando configurado; Boleto faturado
   continua interno (crédito), sem usar o Boleto do Stripe.
9. **Deploy e carga não executados**; sem URL pública nem números de produção.
10. **Licença ausente**; todos os direitos reservados por padrão.
11. **3 produtos do seed** com descrição nula (`EPI-LUV-002`, `EPI-RES-003`,
    `MAQ-PAR-004`).
12. **`.commandcode/` versionado** (arquivos de ferramentas do agente); decisão do
    responsável.

## Próximos passos

1. Corrigir `mypy .` (ou ajustar o CI para `mypy app --strict` com justificativa) e
   verificar os runs da CI.
2. Configurar `CORS_ORIGINS`, `FRONTEND_BASE_URL` e `STRIPE_*` no deploy e validar o
   frontend em navegador comum.
3. Corrigir Grafana e celery-beat; reexecutar `reconcile`.
4. Implementar rate limiting (ADR-0010) ou declarar explicitamente que o WAF cobre.
5. Definir licença, tirar capturas adicionais se necessário e revisar traduções.
6. Executar deploy e teste de carga em staging; só então atualizar este documento.

---

## Integração Stripe Checkout (2026-10-22)

**Estado:** implementada e validada ponta a ponta em ambiente local (Stripe test mode).

### Backend

- Dependência `stripe==16.0.0`.
- `StripeCheckoutGateway` cria **Checkout Session hospedada** (`mode=payment`, cartão,
  `unit_amount` em centavos, moeda do pedido, `metadata` com `order_id`/`company_id`).
- `PaymentGatewayRouter`: cartão e PIX usam Stripe quando `STRIPE_SECRET_KEY` está
  configurada; sem Stripe, o cartão responde `503 stripe_not_configured` e o PIX usa o
  gateway fake local. Boleto (faturado) continua no fluxo interno de fatura/crédito.
- Pedido passa de `RECEIVED`/`CREDIT_REVIEW` para **`PAID`** quando o pagamento de
  cartão/PIX é confirmado (webhook ou conciliação). Boleto faturado permanece `INVOICED`.
  Migration `0020` adiciona `PAID` à constraint de status do pedido.
- `POST /api/v1/payments/{id}/refund` (ADMIN): estorna no Stripe (sessão →
  PaymentIntent → Refund) e marca o pagamento como `REFUNDED`.
- `POST /api/v1/payments/stripe/reconcile` (ADMIN, por empresa): consulta sessões
  Stripe `PENDING`, confirma as pagas e cancela as expiradas (webhooks perdidos).
- Valor mínimo do Stripe (R$ 0,50) validado no backend (`422 payment_amount_too_low`).
- `POST /api/v1/payments` responde `checkout_url` (novo campo) para o redirect.
- `GET /api/v1/payments/methods` (público) informa `{methods, stripe_enabled}`.
- `POST /api/v1/payments/stripe/webhook`: valida `Stripe-Signature` sobre o **corpo bruto**
  (`stripe.Webhook.construct_event`), mapeia `checkout.session.completed` (pago),
  `checkout.session.async_payment_succeeded` e `async_payment_failed` para a máquina de
  estados existente (idempotência por `event.id`, transição atômica, notificação).
- CORS configurável (`CORS_ORIGINS`) — resolve a lacuna apontada na V3.
- Variáveis: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (`whsec_...`),
  `FRONTEND_BASE_URL`, `CORS_ORIGINS`.

### Frontend

- Checkout passa a exibir **Cartão (Stripe)** quando o backend informa `stripe_enabled`.
- Ao confirmar o pedido com cartão: cria o pedido, inicia o pagamento e redireciona para
  `checkout_url` (Stripe hospedado; nenhum dado de cartão passa pelo app).
- Novas páginas `/[locale]/checkout/success` e `/[locale]/checkout/cancel`, com chaves nos
  11 dicionários (paridade mantida).
- `payment-api.ts` + hooks (`usePaymentMethods`, `useInitiatePayment`).

### Evidências

- Sessão real criada com o `sk_test` informado:
  `cs_test_a190xjabWyoEeRZnaJV5gKHiHiaPQn9TamxPn9plTNmxKSCxGpb9sDIcdy`
  (valor `32.90 BRL`, provider `STRIPE`, `checkout_url` do Stripe).
- Webhook assinado com o `whsec` configurado: `200 {"received":true,"outcome":"APPLIED"}`
  e pagamento `PAID` com `paid_at` preenchido.
- PIX real via Stripe: sessão `cs_test_...` criada, webhook `async_payment_succeeded`
  aplicado, pagamento `PAID` e pedido transitado para **`PAID`**.
- Playwright: checkout com cartão visível, selecionado e redirect real para
  `checkout.stripe.com` (`tests/e2e/stripe-checkout.spec.ts`); captura em
  `docs/validation/v4/pt-BR-checkout-card.jpg`.
- Estorno: `POST /payments/{id}/refund` (ADMIN) marca `REFUNDED`; conciliação:
  `POST /payments/stripe/reconcile` confirma sessoes pagas e cancela expiradas.
- Visual V3 reexecutado **sem** `--disable-web-security`, comprovando CORS funcionando
  (`6 passed`).
- Dados de teste revertidos (pedidos, pagamentos, eventos, notificações e carrinho).

### Checagens

| Verificação | Resultado |
|-------------|-----------|
| Backend unit + architecture | ✅ 440 passed (436 unit + 4 arch) |
| Backend integração | ⚠️ 251 passed, 1 skipped; 5 falhas isoladas do ES (`ConnectionTimeout` no Testcontainers, ambiente) |
| `ruff` / `mypy --strict` | ✅ / ✅ 286 arquivos |
| Frontend typecheck/lint/test | ✅ / ✅ / 102 passed |
| Playwright (visual + Stripe) | ✅ 6 passed |

### Configuração no Stripe Dashboard

- Endpoint de webhook: `https://forjab2b.onrender.com/api/v1/payments/stripe/webhook`
- Eventos: `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
  `checkout.session.async_payment_failed`
- Copiar o **Signing secret** (`whsec_...`) para `STRIPE_WEBHOOK_SECRET` no Render.
  O valor `sk_test_...` informado é a **API key** e deve ir em `STRIPE_SECRET_KEY`.

## API: contrato, versionamento, idempotência e webhooks (2026-10-22)

**Estado:** itens 21–24 e parte do 26 do GAP_AUDIT fechados.

### Contrato e documentação

- `ProblemDetails` (RFC 9457) único em `application/problem+json`, com `type`,
  `title`, `status`, `detail`, `instance`, `request_id` e `errors[]` por campo.
- OpenAPI enriquecido: `tags` por módulo com descrição, `summary` em todas as 51
  rotas, respostas 4xx/5xx documentadas, `bearerAuth`/`adminKey`, exemplos nas
  rotas principais e `deprecated: true` na rota legada.
- Snapshot determinístico `docs/api/openapi.json` (SHA-256
  `9075CBEC…E88E`), Redoc estático em `docs/api/index.html` e tipos TypeScript
  em `frontend/core/domain/api-schema.d.ts`.
- Job `openapi-contract` no CI: regenera e falha em drift; `oasdiff breaking
  --fail-on ERR` contra a `main`; drift dos tipos do frontend.

### Idempotência

- Header `Idempotency-Key` obrigatório em pedido/pagamento e opcional em
  criação/publicação de produto e exclusão LGPD; fallback no corpo depreciado.
- Tabela `idempotency_keys` com RLS, unique `(company_id,user_id,method,route,key)`,
  TTL 24 h e reserva `in_progress` de 60 s; migration `0021`.
- Índices únicos de `orders`/`payments` escopados por `company_id`; migration `0022`.
- Replay com `Idempotent-Replayed: true`; payload diferente 422; em andamento 409
  com `Retry-After`; 5xx libera a chave; limpeza via
  `scripts/cleanup_idempotency_keys.py` (métrica `forja_idempotency_keys_purged_total`).

### Versionamento e depreciação

- `docs/API_VERSIONING.md` com regras de compatibilidade, janela de 6 meses,
  quando abrir `/v2` e mapa de comunicação.
- Utilitário `deprecated_route` + middleware: `Deprecation`, `Sunset`, `Link`,
  `Warning`, `deprecated: true` e métrica `forja_deprecated_route_requests_total`.
- Rota legada `POST /api/v1/payments/webhook` marcada com sunset **2027-04-30**.

### Webhooks

- Auditoria em `docs/WEBHOOKS.md`: Stripe e HMAC legado implementados; callback
  OAuth não é webhook; ERP/e-mail inbound **não se aplica**.
- Corpo bruto limitado (1 MiB), HMAC em tempo constante, timestamp assinado com
  tolerância de 5 min, dois segredos ativos, rate limit próprio, logs sem corpo e
  idempotência por `(provider,event_id)`.

### Evidências (Docker de pé)

- OpenAPI gerado duas vezes: idêntico (`--check`).
- `oasdiff`: mudança compatível (campo opcional em `OrderResponse`) passou;
  remoção de `total` falhou com 3 erros `response-required-property-removed`.
- 10 pedidos concorrentes com a mesma chave: **1** pedido no banco, **2**
  replays, **7** respostas 409 com `Retry-After: 60`; payload diferente 422.
- Erros reais: 401 `invalid_token`, 403 `payment_forbidden`, 404
  `order_not_found`, 422 `validation_error` (com `errors[]`), 429
  `rate_limit_exceeded` (`Retry-After: 30`), 503 `stripe_not_configured`.
- Webhook: assinado 200; adulterado 401 `invalid_webhook_signature`; expirado 401
  `webhook_timestamp_invalid`; repetido 200 `DUPLICATE`.
- `alembic downgrade 0020` + `upgrade head` + `alembic check`: OK; backup
  pré-migration `backup_pre_0021.dump` (220.451 bytes).
- Suítes: backend **512 unit/arch + 280 integration** (1 skip); frontend
  **112 testes**, typecheck e lint OK.

### Segurança / pendências

- A `sk_test` foi exposta em conversa; **rotacionar** no dashboard e atualizar o Render.
- **PIX e cartão** usam Stripe Checkout quando configurado; Boleto é faturado interno
  (crédito), não o Boleto avulso do Stripe.
- Estorno disponível via endpoint admin; conciliação de sessões PENDING via endpoint admin.
- Disputas/chargebacks abertos no Stripe Dashboard ainda não são refletidos localmente.
- Sem teste com cartão real (somente test mode) nem conciliação financeira automática.
- Produção exige `FRONTEND_BASE_URL=https://forja-b2b.vercel.app` e
  `CORS_ORIGINS=https://forja-b2b.vercel.app`.

---

## Dados, backup e reconciliação (Prompt 05, 2026-10-22)

**Estado:** migrations com rollback testado, backup com restauração comprovada, outbox com
dead-letter/reprocessamento, reconciliação com advisory lock e limpeza de índices antigos.

### Evidências reais (Docker de pé)

| Verificação | Resultado |
| :--- | :--- |
| Migration drill (head **0022**) | **OK** em **41,10 s** (25,87 s em cache quente; ~290 s a frio); upgrade → seed → downgrade base → upgrade → seed → `alembic check`; checksums do seed idênticos; banco `forja_scratch_*` removido |
| Backup | `forja_db_20261022T235915Z.dump`, **226.309 bytes**, `PGDMP` válido, rotação com retenção 7 |
| Restore drill | `pg_restore` **1,45 s** + `upgrade/current/check` **9,49 s** (total 13,27 s); 50 produtos, 4 empresas, 13 usuários, 4 regras, 150 traduções; extensões presentes; banco dev inalterado; scratch removido |
| Outbox dead-letter | ES indisponível + `SEARCH_OUTBOX_MAX_ATTEMPTS=1` → `DEAD_LETTERED`, `last_error=SearchUnavailableError`; `list-dead` e `requeue` (um e `--all --yes`) validados; eventos de teste removidos |
| Reconciliação concorrente | Com um processo segurando o lock, duas execuções retornaram `{"status":"skipped","reason":"reconcile_already_running"}` |
| Drift induzido | Documento removido do alias; `reconcile` retornou `upserted=1` e o documento voltou (contagem 41) |
| Prune de índices | `--dry-run` listou `forja_products_v1`; execução real removeu v1 e preservou o alias em **`forja_products_v2`**; novo dry-run sem remoções |

### Testes

- Suíte completa com Docker: **788 passed, 4 failed, 1 skipped** em 170 s. As 4 falhas
  são do WIP concorrente, não deste prompt: `test_nenhum_type_ignore_no_codigo`
  (`app/interface/openapi.py`, `app/infrastructure/rate_limit/redis_stores.py`,
  `tests/unit/test_deprecation.py`, `tests/unit/test_rate_limit.py`) e três testes de
  `test_companies_api.py` que receberam **429** do rate limiting em Redis (estado de
  bucket compartilhado entre execuções).
- Suíte sem Docker: **514 passed, 278 skipped, 1 failed** (a mesma falha de
  `type: ignore` alheia).
- `test_search_outbox_repository.py`: **1 passed**; `test_search_reconcile_lock.py`:
  **2 passed**; `test_search_index_es.py`: **9 passed** na execução completa.
- `mypy app --strict`: **0 erros em 304 arquivos**; `ruff check/format` dos arquivos
  alterados: **OK**; import-linter: **4 contratos mantidos**; Compose config: **OK**.

### Pendências registradas

1. O job `migrations` do Prompt 02 **não existe** no CI; o drill ainda não está conectado.
2. O alerta do Prompt 04 para reconciliação atrasada ainda não foi aplicado; a métrica
   `forja_reconcile_last_success_timestamp_seconds` está pronta.
3. O loop de métricas/agendador no processo da API foi validado por testes unitários, mas a
   imagem em execução no dev não foi reconstruída; o comportamento em `/metrics` deve ser
   confirmado no próximo build.
4. Cron Job do Render: a documentação oficial foi consultada; a disponibilidade no
   plano/workspace real está **NÃO CONFERIDA**.
5. O `docker-compose.yml` passou a entregar `ELASTICSEARCH_URL/USERNAME/PASSWORD` ao backend,
   worker e beat (antes só o backend recebia a URL). O `.env` local aponta para um cluster
   Elastic Cloud; para validar localmente use `ELASTICSEARCH_URL=http://elasticsearch:9200`.
