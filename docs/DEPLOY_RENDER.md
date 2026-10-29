# Deploy no Render — estado e pendências

> **Status: NÃO EXECUTADO.** Não há `render.yaml`, Blueprint, URL pública, job de deploy ou
> evidência de execução no Render neste repositório. O texto abaixo é um roteiro de
> trabalho, não um relato de deploy.

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
- `DATABASE_ADMIN_URL` **somente** no job de migration/seed (role `forja_admin`), nunca no
  runtime
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
3. Rodar migrations como job one-off (`alembic upgrade head`) antes de liberar tráfego.
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
