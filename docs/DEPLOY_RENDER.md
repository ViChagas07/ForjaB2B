# Deploy no Render — estado e pendências

> **Status:** o backend está publicado no Render e é consumido pelo frontend no Vercel via
> proxy `/api/v1`; a configuração do serviço vive no dashboard, não neste repositório. Não há
> `render.yaml`/Blueprint versionado: o texto abaixo é o roteiro reproduzível, e divergências
> em relação ao serviço real devem ser corrigidas no dashboard ou versionadas como Blueprint.

## Pre-deploy de migrations (obrigatório)

O código nunca deve subir esperando colunas que o banco ainda não possui. O Render executa
o comando de pre-deploy com a imagem da **nova** versão, antes de liberar tráfego; se ele
falhar, o deploy é abortado. Configure no serviço da API:

1. **Settings → Pre-Deploy Command:** `python scripts/predeploy.py`
2. **Environment:** `DATABASE_ADMIN_URL` com a URL da role de migrations (`forja_admin`),
   nunca a role de runtime (`forja_app`). Marque como secret. A role não precisa
   ser owner das tabelas pré-existentes nem ter `REFERENCES` nelas: a migration
   0042 (`order_item_pricing`) só cria uma tabela nova, sem FK. O predeploy
   exige apenas `CREATE` no schema `public` e avisa sobre ownership.
3. O script valida `CREATE` em `public`, aplica `alembic upgrade head`, confere que a
   revisão atual é o head e só então retorna 0. Ownership de tabelas existentes é
   verificado pelo próprio Alembic (transacional): se a role não puder alterar, o erro
   real aparece no log. Credencial errada ou migration pendente/falha encerram com
   código 2 e bloqueiam o pre-deploy.

O pre-deploy exige instance type pago no Render. Em plano free, a imagem da API executa
`scripts/start_api.sh` antes do `uvicorn`: se `DATABASE_ADMIN_URL` estiver presente, aplica
`alembic upgrade head` (com advisory lock entre instâncias) e só então libera o tráfego;
`RUN_MIGRATIONS_ON_STARTUP=false` desabilita esse passo. Se a migration falhar, o startup
registra o erro mas inicia a API em modo de compatibilidade (login/CNPJ funcionam, cadastro
CPF responde 503); `GET /health/schema` informa `outdated`. Se a variável não existir,
vale o mesmo modo de compatibilidade — corrija configurando `DATABASE_ADMIN_URL` com uma
role que tenha ownership/DDL e faça um novo deploy. Em banco gerenciado que expõe apenas a
role principal do PostgreSQL (por exemplo, `forja` no Render), essa mesma role pode ser
usada como admin desde que o preflight confirme ownership e `CREATE`.

Em banco gerenciado novo, o bootstrap de `docker/postgres` (roles, schema `app`, funções RLS)
deve ser aplicado uma vez, de forma idempotente, antes da primeira migration que referencia
as roles dedicadas `forja_recovery`/`forja_chat` (revisões 0025/0026).

## O que existe no repositório

- `backend/Dockerfile` e `backend/Dockerfile.worker` (imagens separadas).
- `frontend/Dockerfile` (Next.js `standalone`).
- `docker-compose.yml` para desenvolvimento e `docker-compose.prod.yml` para o
  Elasticsearch com TLS/API key em VPS. **Nenhum dos dois é um blueprint de Render.**
- `.github/workflows/` com lint, testes, build de imagens e scan; não há job de deploy.
- `docs/search/RUNBOOK.md` com o procedimento de Elasticsearch em VPS/Elastic Cloud.

## Arquitetura de destino sugerida

| Componente | Opção no Render | Observação |
| :--- | :--- | :--- |
| API | Web Service (Docker, `backend/Dockerfile`) | Health check em `/health/live`; readiness em `/health/ready` |
| Worker/beat | Background Worker (Docker, `backend/Dockerfile.worker`) | Beat separado ou scheduler; ver falha local do beat |
| Frontend | Web Service (Docker, `frontend/Dockerfile`) | `BACKEND_URL` (somente servidor) alimenta o rewrite same-origin para `/api/v1` |
| PostgreSQL | Render PostgreSQL | **Verificar suporte a `vector`/pgvector** na versão oferecida; se não houver, desabilitar embeddings |
| Redis | Render Key Value | Refresh, cache, OAuth state/exchange, rate limiting (fail-open geral e fail-closed na recuperacao) |
| Elasticsearch | Elastic Cloud ou VPS | Render não oferece Elasticsearch gerenciado; usar HTTPS + API key |
| Objetos estáticos | Disco persistente ou storage | O projeto serve SVGs versionados; não gravar em disco efêmero |

## Variáveis e segredos

Criar **Environment Groups** no Render (ou Secret Files) e referenciar por serviço. Nunca
versionar valores. O `.env.example` é apenas desenvolvimento.

- `ENVIRONMENT=production`, `LOG_LEVEL`, `LOG_FORMAT=json`
- `DATABASE_URL` (runtime, role `forja_app`)
- `DATABASE_ADMIN_URL` (role com DDL/ownership): usada no pre-deploy e no startup; no
  runtime também alimenta o engine administrativo do catálogo. Em banco gerenciado com uma
  única role principal (ex.: `forja` no Render), é aceitável usar essa role, desde que o
  preflight confirme ownership e `CREATE`. Em VPS/Compose, prefira `forja_admin`.
- `DATABASE_ADMIN_ROLE` (opcional): quando `DATABASE_ADMIN_URL` usa a role principal do
  Render e ela é membro de `forja_admin` com `SET`, defina `forja_admin` para o Alembic
  iniciar a conexão já como owner. Exemplo pontual:
  `GRANT forja_admin TO forja WITH SET TRUE`, rode a migration e depois
  `REVOKE forja_admin FROM forja GRANTED BY forja` para restaurar a membership original.
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `ELASTICSEARCH_URL`, `ELASTICSEARCH_API_KEY`, `ELASTICSEARCH_CA_CERTS`,
  `ELASTICSEARCH_VERIFY_CERTS=true`, `ELASTICSEARCH_INDEX_VERSION`
- `SECRET_KEY`, `PEPPER`, `ENCRYPTION_KEY`, `PAYMENT_WEBHOOK_SECRET`
- `PASSWORD_RECOVERY_ENABLED` (padrão `false`). Quando `true` em produção, o startup exige
  `TURNSTILE_SECRET_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_VERIFY_SERVICE_SID` e `RESEND_API_KEY`; ausência de qualquer uma impede o boot
  (a mensagem lista somente os nomes, nunca os valores).
- `TURNSTILE_SECRET_KEY` (backend; Cloudflare Turnstile, fail-closed).
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID` (Twilio Verify por
  SMS). O backend chama a API HTTP com `httpx`, sem SDK síncrono do Twilio.
- `RECOVERY_CODE_TTL_SECONDS` (padrão `600`), `RECOVERY_CODE_MAX_ATTEMPTS` (padrão `5`) e
  `RECOVERY_RESET_TOKEN_TTL_SECONDS` (padrão `600`) ajustam o fluxo sem novo deploy de código.
- Para o envio da recuperação em produção, configure `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`
  e `RESEND_FROM`; o worker Celery usa a factory existente, que seleciona o
  `ResendEmailSender`. Com `EMAIL_DRY_RUN=true` nenhum e-mail é enviado.
- `RATE_LIMIT_PASSWORD_RECOVERY_IP_CAPACITY` (padrão `10`),
  `RATE_LIMIT_PASSWORD_RECOVERY_IP_REFILL_PER_MINUTE` (padrão `10`),
  `RATE_LIMIT_PASSWORD_RECOVERY_IDENTIFIER_CAPACITY` (padrão `3`),
  `RATE_LIMIT_PASSWORD_RECOVERY_IDENTIFIER_REFILL_PER_MINUTE` (padrão `3`),
  `RATE_LIMIT_PASSWORD_RECOVERY_VERIFY_IP_CAPACITY` (padrão `20`),
  `RATE_LIMIT_PASSWORD_RECOVERY_VERIFY_IP_REFILL_PER_MINUTE` (padrão `20`),
  `RATE_LIMIT_PASSWORD_RECOVERY_VERIFY_IDENTIFIER_CAPACITY` (padrão `10`),
  `RATE_LIMIT_PASSWORD_RECOVERY_VERIFY_IDENTIFIER_REFILL_PER_MINUTE` (padrão `10`),
  `PASSWORD_RECOVERY_DAILY_LIMIT` (padrão `5`) e
  `PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS` (padrão `60`) controlam os baldes
  dedicados; Redis indisponível nesse fluxo resulta em 503 genérico (fail-closed).
- `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (Vercel/frontend; chave PÚBLICA do widget). O secret
  correspondente existe apenas no Render.
- A revogação de sessões pós-reset usa `user_credential_state` (migration `0043`) e o cache
  Redis `credential_epoch:{user_id}` com TTL de 60 s. Aplique a migration antes de subir este
  código; sem a tabela, a checagem de época falha fechada (503).
- Verificação do próprio telefone usa `TWILIO_*` e as migrations `0043`/`0044`. Sem as
  credenciais Twilio, as rotas respondem 503 genérico. `PHONE_VERIFICATION_DRY_RUN` é proibido
  em produção; os limites `RATE_LIMIT_PHONE_VERIFICATION_*`,
  `PHONE_VERIFICATION_DAILY_USER_LIMIT`, `PHONE_VERIFICATION_DAILY_IP_LIMIT` e
  `PHONE_VERIFICATION_RESEND_COOLDOWN_SECONDS` são ajustáveis.
- O reset por SMS usa o mesmo `TWILIO_VERIFY_SERVICE_SID`: o envio é enfileirado na task
  `app.tasks.password_recovery.send_password_reset_sms` e o código é gerado/checado pelo
  Twilio Verify (nunca armazenado em claro).
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
  `GOOGLE_OAUTH_FRONTEND_REDIRECT` (se OAuth for usado). O
  `GOOGLE_OAUTH_FRONTEND_REDIRECT` deve ser a página do frontend
  (`https://forja-b2b.vercel.app/pt-BR/auth/google/callback`), nunca o caminho
  `/api/v1/auth/google/callback`; o backend também normaliza esse erro para
  evitar loop, mas a configuração correta é a da página.
- `BACKEND_URL` (frontend, somente servidor: destino dos rewrites `/api/v1` e `/static`)
- `TRUSTED_PROXY_COUNT`: local `0`; Render direto `1`; com Vercel na frente do
  Render, valide a cadeia `X-Forwarded-For` (normalmente `2`). Se ficar `0` ou
  `1` com dois proxies, o rate limit por IP pode compartilhar o mesmo balde
  entre usuários.
- `DEMO_USER_PASSWORD` **não** deve existir em produção; o seed é recusado por padrão e
  exige `SEED_ALLOW_PRODUCTION=true` para rodar conscientemente

## Passos necessários (nenhum executado)

1. Criar o Blueprint ou os serviços manualmente; configurar health checks e autoscaling.
2. Criar o PostgreSQL/Redis gerenciados e validar extensões (`vector`, `unaccent`,
   `pg_trgm`) e roles. O bootstrap atual (`docker/postgres/init-roles.sql`) roda no initdb
   do Compose; em banco gerenciado, aplicar roles/ACLs por job idempotente.
3. Rodar migrations automaticamente no pre-deploy (`python scripts/predeploy.py`), que
   aborta o deploy se o banco não estiver no head.
4. Fazer seed **somente** se for uma demonstração; em produção real, não.
5. Criar o índice de busca (`bootstrap --version 2`, `reindex --version 2`) e configurar
   `reconcile` no scheduler.
6. Configurar `BACKEND_URL` no frontend e confirmar o proxy same-origin `/api/v1`; o CORS
   do backend permanece disponível para chamadas diretas em desenvolvimento.
7. Configurar logs/métricas (OTel/Prometheus) e alertas; o Grafana local está quebrado.
8. Validar login, catálogo, busca, preço por empresa, carrinho, pedido, admin e i18n em
   produção.
9. Registrar URL, commit, data, resultados e limitações; só então remover o aviso
   “NÃO EXECUTADO” deste documento.

## Riscos específicos do Render

- **Disco efêmero:** não gravar imagens/arquivos em disco local; usar storage ou manter os
  assets versionados.
- **Conexões:** pool do PostgreSQL e limite de conexões do plano; o backend usa pool
  explícito e pode esgotar conexões com muitos workers.
- **Elasticsearch fora do Render:** latência entre provedores e custo de egress; TLS e API
  key obrigatórios.
- **pgvector:** se o plano gerenciado não suportar a extensão, `EMBEDDINGS_ENABLED` fica
  `false` e a busca é lexical + fallback.
- **CORS/proxy:** resolver antes de considerar o frontend utilizável.
- **Segredos:** rotação e escopo por serviço; não reutilizar o `.env` de desenvolvimento.

## O que ainda falta para dizer “deployado”

- `render.yaml` versionado (ou configuração equivalente documentada).
- Execução real com URL pública e health check verde.
- Migrations/seed/index aplicados e verificados.
- Evidência de login, busca, preço por empresa e admin em produção.
- Capturas e relatório de validação.

## Recuperacao de conta

Checklist completo, ordem segura de ativacao, Cloudflare Hostnames, verificacao de
dominio no Resend, Twilio trial, custo de SMS e roteiro manual estao em
[PASSWORD_RECOVERY.md](PASSWORD_RECOVERY.md).
