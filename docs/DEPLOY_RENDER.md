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
   nunca a role de runtime (`forja_app`). Marque como secret.
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
| Redis | Render Key Value | Refresh, cache, OAuth state/exchange; não há rate limiting |
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
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `ELASTICSEARCH_URL`, `ELASTICSEARCH_API_KEY`, `ELASTICSEARCH_CA_CERTS`,
  `ELASTICSEARCH_VERIFY_CERTS=true`, `ELASTICSEARCH_INDEX_VERSION`
- `SECRET_KEY`, `PEPPER`, `ENCRYPTION_KEY`, `PAYMENT_WEBHOOK_SECRET`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
  `GOOGLE_OAUTH_FRONTEND_REDIRECT` (se OAuth for usado)
- `BACKEND_URL` (frontend, somente servidor: destino dos rewrites `/api/v1` e `/static`)
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
