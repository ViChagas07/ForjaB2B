# Runbook Operacional - Forja B2B (DevOps & SRE)

Este documento descreve os procedimentos operacionais padrão (SOP), contingência, monitoramento e troubleshooting para o ambiente Forja B2B.

---

## 1. Visão Geral da Arquitetura de Serviços

| Serviço | Porta Interna | Porta Host | Finalidade | Healthcheck |
| :--- | :--- | :--- | :--- | :--- |
| `postgres` | 5432 | 5432 | Banco relacional com RLS e extensões | `pg_isready -U postgres` |
| `redis` | 6379 | 6379 | Cache e Broker Celery | `redis-cli ping` |
| `elasticsearch` | 9200 | 9200 (só loopback) | Busca lexical (Elasticsearch 9) | `curl -u elastic:... /\_cluster/health?wait_for_status=yellow` |
| `backend` | 8000 | 8000 | API FastAPI (Python 3.12) | `GET /health` via curl |
| `celery_worker`| - | - | Tarefas assíncronas em background | `celery inspect ping` |
| `celery_beat` | - | - | Agendador de tarefas periódicas | Process liveness |
| `frontend` | 3000 | 3000 | Interface Next.js (Node 20) | `GET /api/health` via wget |
| `otel-collector` | 4317 (gRPC) / 4318 (HTTP) | 4317 / 4318 | Ingestão e roteamento de telemetria | Endpoint 13133 |
| `prometheus` | 9090 | 9090 | Coleta e armazenamento de métricas TSDB | `GET /-/healthy` |
| `grafana` | 3000 | 3001 | Visualização (Dashboards & Alertas) | `GET /api/health` |

---

## 2. Como Subir e Derrubar o Ambiente

### 2.1. Inicialização

1. Copiar variáveis de ambiente:
   ```bash
   cp .env.example .env
   # Preencher chaves secretas e credenciais reais
   ```
2. Iniciar todos os serviços via Compose ou Makefile:
   ```bash
   make up
   # ou
   docker compose up -d
   ```
3. Verificar status da stack:
   ```bash
   make ps
   # ou
   docker compose ps
   ```

### 2.2. Parada e Limpeza

- Parar serviços mantendo volumes e dados:
  ```bash
  make down
  # ou
  docker compose down
  ```
- Parar e destruir volumes (ATENÇÃO: apaga dados do PostgreSQL e Redis):
  ```bash
  make down-volumes
  # ou
  docker compose down -v
  ```

---

## 3. Onde Olhar Quando o Sistema Falhar

### 3.1. Roteiro Rápido de Diagnóstico (Triage)
1. **Verificar containers caídos ou reiniciando:**
   ```bash
   docker compose ps
   ```
2. **Consultar logs do serviço com erro:**
   ```bash
   make logs-backend
   make logs-worker
   make logs-postgres
   ```
3. **Acessar Grafana:**
   - URL: `http://localhost:3001` (Usuário: `admin`, Senha: `${GRAFANA_ADMIN_PASSWORD}`)
   - Dashboards provisionados em `Dashboards -> Forja B2B Overview`.
4. **Verificar métricas brutas e alertas no Prometheus:**
   - URL: `http://localhost:9090/alerts` e `http://localhost:9090/targets`
   - Checar se todos os targets estão em estado `UP`.
5. **Verificar saúde do OpenTelemetry Collector:**
   - Health check: `http://localhost:13133/` (responde `HTTP 200` com corpo `{"status":"Server available",...}`)
   - Métricas internas do coletor: `http://localhost:8888/metrics`
   - O `healthcheck` do Compose usa o próprio binário do collector
     (`/otelcol-contrib validate`) porque a imagem oficial é `FROM scratch`
     (sem shell, `curl` ou `wget`) e o upstream não fornece um binário
     `/healthcheck` (issue #30798). O endpoint `:13133` acima é a sonda de
     liveness real (extensão `health_check`) e o target Prometheus
     `otel-collector` (scrape em `:8889`) é a verificação externa contínua.

---

## 4. Banco de Dados: Roles, RLS e Backups

### 4.1. Roles e Segurança
- O bootstrap do initdb executa `docker/postgres/01-init-roles.sh` e `docker/postgres/02-rls-setup.sh`, que invocam os SQLs em `/docker-entrypoint-initdb.d/sql/` com as credenciais do ambiente (nenhuma senha fica nos arquivos SQL).
- **Bootstrap (`POSTGRES_BOOTSTRAP_*`)**: superusuário efêmero usado apenas no initdb do cluster; nunca é injetado no backend/worker.
- **`forja_admin`**: role restrita (`NOSUPERUSER`, `NOBYPASSRLS`) para migrações do Alembic/DBA; é owner do database, não superusuário.
- **`forja_app`**: usuário de runtime da aplicação, obrigado a respeitar políticas RLS (`NOBYPASSRLS`), com DML apenas.
- Contexto de tenant é injetado por transação via `SELECT app.set_tenant_context(:company_id, :user_id)`, que define as GUCs `forja.current_company_id` e `forja.current_user_id` com escopo local (`SET LOCAL` equivalente). A função não autentica nem autoriza: o backend deve derivar os valores de identidade autenticada.
- Integração backend: `app.infrastructure.db.unit_of_work.SqlAlchemyUnitOfWork` aplica o contexto DENTRO da mesma transação das consultas (`async with uow_factory.begin(tenant)`). Como as GUCs têm escopo de transação e o pool usa `pool_reset_on_return="rollback"`, nenhum contexto de tenant vaza entre requests que reutilizam conexões.

### 4.1.1. Resolução de identidade no login (Fase 2)

Como `users` tem `FORCE ROW LEVEL SECURITY` e a policy padrão exige
`company_id = app.current_company_id()`, a aplicação não consegue localizar o
usuário por e-mail **antes** de conhecer o tenant. A solução é uma função
`SECURITY DEFINER` no schema `app`:

- **`app.resolve_user_by_email(p_email TEXT)`** (`SECURITY DEFINER`, `STABLE`,
  `SET search_path = public, pg_temp`): retorna apenas
  `(user_id, company_id, status, password_hash)` de um único e-mail. A função
  recebe o e-mail como parâmetro tipado (sem SQL dinâmico) e não é um mecanismo
  genérico de bypass de RLS.
- **`forja_auth`** (role dedicada, `NOLOGIN`, `NOBYPASSRLS`, `NOSUPERUSER`):
  owner da função. É alcançável somente pela função; a role tem apenas
  `USAGE, CREATE` no schema `app` e uma política RLS dedicada
  (`users_auth_lookup`, migration `0006`) que permite a leitura mínima de
  `users` apenas para essa role. O runtime (`forja_app`) tem apenas `EXECUTE`
  na função e continua impossibilitado de ler `users` sem contexto de tenant.

A verificação da senha (Argon2id) e a emissão dos tokens acontecem na
aplicação; o banco nunca recebe a senha em texto plano. A role `forja_admin`
é membro de `forja_auth` (com `NOINHERIT`) somente para permitir a
transferência de ownership da função no bootstrap.

### 4.1.2. Fronteira bootstrap vs. Alembic

| Responsabilidade | Onde vive | Executado por |
| :--- | :--- | :--- |
| Roles, ACLs, extensoes, schema `app`, funcoes `app.*` (RLS helpers) | `docker/postgres/*.sql` (initdb) | Uma vez no bootstrap do cluster |
| Schema de dominio (tabelas, indexes, policies RLS de dominio) | `backend/alembic/versions/` (Fase 1+) | `make migrate` (one-off com `forja_admin`) |

- O `alembic/env.py` le **somente** `DATABASE_ADMIN_URL` e falha explicitamente sem ela; a role de runtime (`forja_app`, `DATABASE_URL`) nao tem privilegio de DDL por desenho.
- `include_object` no `env.py` bloqueia qualquer objeto do schema `app`, impedindo que autogenerate futuro toque a fundacao RLS.
- `make migrate` sobe um container one-off (`docker compose run --rm --no-deps --env-file .env`) com a imagem do backend; os containers de runtime nunca recebem `DATABASE_ADMIN_URL`.

### 4.2. Backup Manual do PostgreSQL
```bash
make db-backup
# Cria arquivo compactado em backups/backup_YYYYMMDD_HHMMSS.sql.gz
```

### 4.3. Restauração de Backup
1. Descompactar o arquivo desejado:
   ```bash
   gunzip -k backups/backup_YYYYMMDD_HHMMSS.sql.gz
   ```
2. Executar restauração:
   ```bash
   docker compose exec -T postgres psql -U postgres -d forja_db < backups/backup_YYYYMMDD_HHMMSS.sql
   ```
3. Reaplicar permissões de roles caso necessário (os wrappers leem as credenciais do ambiente do container):
   ```bash
   docker compose exec -T postgres bash /docker-entrypoint-initdb.d/01-init-roles.sh
   docker compose exec -T postgres bash /docker-entrypoint-initdb.d/02-rls-setup.sh
   ```

---

## 5. Procedimento de Rollback

### 5.1. Rollback de Aplicação (Backend / Frontend)
1. Identificar tag/commit estável anterior.
2. Atualizar tags das imagens no arquivo de configuração / deploy.
3. Executar o deploy da versão anterior:
   ```bash
   docker compose up -d --no-deps backend
   # ou
   docker compose up -d --no-deps frontend
   ```

### 5.2. Rollback de Migrações de Banco (Alembic)
1. Reverter a última migração com a role administrativa (container one-off):
   ```bash
   make migration-rollback
   ```
2. Verificar versão atual do schema:
   ```bash
   docker compose run --rm --no-deps --env-file .env backend alembic current
   ```

---

## 6. Checklist de Contingência e Alertas Críticos

- **Banco PostgreSQL Inacessível**:
  - Testar conectividade: `docker compose exec postgres pg_isready -U postgres`
  - Checar espaço em disco e se o volume `postgres_data` está íntegro.
- **Memória / OOMKilled**:
  - Verificar eventos de término: `docker events --filter 'event=die'`
  - Ajustar limits de memória em `deploy.resources.limits` se configurado.
- **Fila Celery Travada / Crescendo**:
  - Checar saúde do Redis: `docker compose exec redis redis-cli ping`
  - Inspecionar tarefas ativas: `docker compose exec celery_worker celery inspect active`

---

## 7. Elasticsearch (Busca — Fase 2)

### 7.1. Endereços e credenciais

- **Endereço interno (containers):** `http://elasticsearch:9200` — valor de `ELASTICSEARCH_URL`; é o usado pelo backend.
- **Endereço no host:** `http://localhost:9200` — a porta é publicada **somente no loopback** (`127.0.0.1:9200:9200`), nunca em `0.0.0.0`.
- **Credenciais:** `ELASTICSEARCH_USERNAME` / `ELASTICSEARCH_PASSWORD` (arquivo `.env`). Em dev usa-se o usuário `elastic` (superuser); um usuário de aplicação com privilégios mínimos fica para a Fase 6.
- **Desligar a integração:** `ELASTICSEARCH_ENABLED=false` — o backend sobe normalmente e `GET /health/search` reporta `disabled`.
- **Versões (Fase 8A):** servidor `docker.elastic.co/elasticsearch/elasticsearch:9.5.5` e cliente Python `elasticsearch[async]==9.5.1` — **mesma major (9)**. Em qualquer ambiente gerenciado, a major do deployment do ES deve ser a mesma do cliente Python.

### 7.2. Segurança (decisão de desenvolvimento)

- `xpack.security` fica **habilitado** com autenticação por senha. **Nunca** desabilitar.
- Em desenvolvimento usa-se **HTTP sem TLS** apenas na rede interna do Docker, com autenticação — decisão explícita de dev. **TLS é obrigatório em produção** (Fase 6); a verificação de TLS nunca é desabilitada no cliente.
- `ELASTICSEARCH_API_KEY` é opcional e destinada a produção.

### 7.3. Health check

```bash
# Do host (loopback) — usa a senha do .env
curl -u "elastic:$ELASTICSEARCH_PASSWORD" \
  "http://localhost:9200/_cluster/health?wait_for_status=yellow"
# Dentro do Docker — usa a variável ELASTIC_PASSWORD do container
docker compose exec elasticsearch \
  curl -fsS -u "elastic:$ELASTIC_PASSWORD" \
  "http://localhost:9200/_cluster/health?wait_for_status=yellow"
```

O endpoint da aplicação `GET /health/search` reporta `ok` / `degraded` / `unavailable` / `disabled` e **nunca** derruba o readiness. O readiness (`/health/ready`) continua dependendo apenas de PostgreSQL e Redis — o Elasticsearch **não** é essencial ao startup.

### 7.4. Requisitos de sistema

- **Linux:** `sudo sysctl -w vm.max_map_count=262144` (persistir em `/etc/sysctl.d/99-elasticsearch.conf`). Sem isso, o Elasticsearch 9 pode falhar ao iniciar.
- **Docker Desktop (Windows/macOS) com WSL2:** reservar memória para Elasticsearch + PostgreSQL + Redis + backend (recomendado **≥ 6–8 GB**). O container do Elasticsearch tem `mem_limit: 1536m` e heap `-Xms512m -Xmx512m`.
- **Volume:** usa volume nomeado próprio (`elasticsearch_data` / `forja_elasticsearch_data`). **Nunca** remova ou recrie volumes (`docker compose down -v` é proibido).

### 7.5. Operação

```bash
docker compose up -d elasticsearch     # sobe apenas o Elasticsearch
docker compose stop elasticsearch      # para o serviço (preserva os dados)
docker compose logs -f elasticsearch   # acompanha os logs
```

> **Atenção (volume pré-existente):** habilitar segurança sobre um volume que foi inicializado antes com `xpack.security.enabled=false` pode fazer o Elasticsearch recusar a senha configurada. **Não** apague o volume: pare o serviço, inspecione-o (`docker volume inspect forja_elasticsearch_data`) e só então siga um procedimento que **preserve os dados** antes de qualquer recriação.

> **Atenção (upgrade 8.15 → 9.5.5, achado real da Fase 7):** o ES 9 recusa subir sobre um volume do
> **8.15.0** ("upgrade to version [8.19.0] first"). Procedimento **não destrutivo** (mesmo volume):
> subir `docker.elastic.co/elasticsearch/elasticsearch:8.19.0` apontando para o volume, aguardar
> `healthy`, parar, e então subir `9.5.5`. Nunca use `down -v` nem remova o volume.
> **Só se aplica a volumes antigos criados em 8.x** — uma instalação **do zero** sobe direto no
> `9.5.5` e não passa por esse passo.

### 7.6. Índice, reindexação, busca e deploy (Fases 3–6)

O guia completo — variáveis, criação/reconstrução do índice, busca em cada modo, fallback,
smoke test, deploy em produção (VPS e Elastic Cloud), observabilidade e limitações — está em
**`docs/search/RUNBOOK.md`**. Comandos essenciais:

```bash
docker compose exec backend python -m app.modules.search.interface.cli bootstrap   # índice + alias
docker compose exec backend python -m app.modules.search.interface.cli reindex     # reconstrói do PG
docker compose exec backend python -m app.modules.search.interface.cli backfill-embeddings  # vetorial
python backend/scripts/smoke_search.py --base-url http://localhost:8000 --sku CAP-001  # pós-deploy
```

- Índice versionado `forja_products_vN` + alias `forja_products` (rollback por troca de alias).
- Fallback: `docker compose stop elasticsearch` → `search_mode=postgres_fallback` (nunca `down -v`).
- Produção VPS: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
  (TLS obrigatório, API key restrita, snapshots). Elastic Cloud: só URL HTTPS + API key.
- Decisão de arquitetura: `docs/ADRs/0004-busca-hibrida.md`.
