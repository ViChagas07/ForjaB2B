# Runbook Operacional - Forja B2B (DevOps & SRE)

Este documento descreve os procedimentos operacionais padrão (SOP), contingência, monitoramento e troubleshooting para o ambiente Forja B2B.

---

## 1. Visão Geral da Arquitetura de Serviços

| Serviço | Porta Interna | Porta Host | Finalidade | Healthcheck |
| :--- | :--- | :--- | :--- | :--- |
| `postgres` | 5432 | 5432 | Banco relacional com RLS e extensões | `pg_isready -U postgres` |
| `redis` | 6379 | 6379 | Cache e Broker Celery | `redis-cli ping` |
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
