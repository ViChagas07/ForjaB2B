-- -----------------------------------------------------------------------------
-- Forja B2B: Roles, credenciais e hardening base (PostgreSQL 16)
-- -----------------------------------------------------------------------------
-- Executado SOMENTE via 01-init-roles.sh no bootstrap do initdb, que injeta as
-- variaveis psql app_user/app_password/admin_user/admin_password/db_name a
-- partir das variaveis de ambiente do container. Nenhuma senha fica gravada
-- neste arquivo.
--
-- Modelo de credenciais:
--   * bootstrap ($POSTGRES_USER): superuser efemero do initdb; nunca exposto
--     ao backend/worker;
--   * forja_admin (admin): DDL/migracoes e operacao DBA; NAO e superuser e
--     NAO tem BYPASSRLS;
--   * forja_app (app): runtime; DML apenas, estritamente sujeita a RLS.
--
-- Reaplicacao: este script e idempotente quanto a criacao/atributos. Ele NAO
-- rotaciona a senha de uma role ja existente (rotacao e procedimento operador).
-- -----------------------------------------------------------------------------

\if :{?app_user}
\else
    \echo 'FATAL: variavel psql app_user ausente. Execute via 01-init-roles.sh.'
    \quit 1
\endif
\if :{?app_password}
\else
    \echo 'FATAL: variavel psql app_password ausente. Execute via 01-init-roles.sh.'
    \quit 1
\endif
\if :{?admin_user}
\else
    \echo 'FATAL: variavel psql admin_user ausente. Execute via 01-init-roles.sh.'
    \quit 1
\endif
\if :{?admin_password}
\else
    \echo 'FATAL: variavel psql admin_password ausente. Execute via 01-init-roles.sh.'
    \quit 1
\endif
\if :{?db_name}
\else
    \echo 'FATAL: variavel psql db_name ausente. Execute via 01-init-roles.sh.'
    \quit 1
\endif

-- 1. Extensoes base do banco operacional
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Hardening do schema public (previne criacao de objetos por roles comuns)
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 3. Role de runtime da aplicacao
--    Login + DML; sem superuser, sem BYPASSRLS, sem privilegios de cluster.
SELECT format(
        'CREATE ROLE %I WITH LOGIN PASSWORD %L '
        'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
        :'app_user', :'app_password')
WHERE NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'app_user')
\gexec

ALTER ROLE :"app_user" WITH
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

-- 4. Role administrativa restrita (migracoes/DDL/operacao DBA)
--    NAO e superuser e NAO tem BYPASSRLS: DDL nao e afetado por RLS, e DML
--    administrativo em tabelas com FORCE RLS exige contexto de tenant definido.
SELECT format(
        'CREATE ROLE %I WITH LOGIN PASSWORD %L '
        'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
        :'admin_user', :'admin_password')
WHERE NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'admin_user')
\gexec

ALTER ROLE :"admin_user" WITH
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

-- 4.5. Role dedicada a resolucao de identidade no login (Fase 2).
--    NOLOGIN: e usada APENAS como owner SECURITY DEFINER da funcao
--    app.resolve_user_by_email (que a aplicacao chama antes de conhecer o
--    tenant, pois a tabela users tem FORCE RLS). A role nao pode logar e o
--    unico objeto que roda como ela e a funcao; a politica RLS especifica
--    (migration 0006) restringe o acesso ao minimo necessario.
--    Ela NAO tem BYPASSRLS: o acesso se da por politica dedicada, nao por
--    bypass indiscriminado.
SELECT 'CREATE ROLE forja_auth NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
       'NOINHERIT NOREPLICATION NOBYPASSRLS'
WHERE NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'forja_auth')
\gexec

ALTER ROLE forja_auth WITH
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

-- forja_admin precisa ser membro de forja_auth apenas para transferir o
-- ownership da funcao app.resolve_user_by_email (SECURITY DEFINER). Como
-- forja_admin tem NOINHERIT, a membership nao e herdada automaticamente:
-- forja_admin continua sujeita a RLS (NOBYPASSRLS) e nao ganha os privilegios
-- de forja_auth de forma silenciosa.
GRANT forja_auth TO :"admin_user";

-- 4.6. Role dedicada ao despacho da outbox de notificacoes (Fase 11).
--    NOLOGIN: usada APENAS como owner SECURITY DEFINER da funcao
--    app.list_due_notifications (que o worker chama para enumerar notificacoes
--    pendentes sem contexto de tenant, pois a tabela notifications tem FORCE
--    RLS). A role nao pode logar e o unico objeto que roda como ela e a funcao;
--    a politica RLS dedicada (migration 0010) restringe o acesso ao minimo.
SELECT 'CREATE ROLE forja_notification NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
       'NOINHERIT NOREPLICATION NOBYPASSRLS'
WHERE NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'forja_notification')
\gexec

ALTER ROLE forja_notification WITH
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

GRANT forja_notification TO :"admin_user";

-- 5. Conectividade restrita ao banco operacional
REVOKE CONNECT ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
GRANT CONNECT ON DATABASE :"db_name" TO :"admin_user";

-- 6. forja_admin administra o database (owner), sem superpoderes de cluster.
--    O owner do database pode criar schemas e objetos para as migracoes.
ALTER DATABASE :"db_name" OWNER TO :"admin_user";

GRANT USAGE ON SCHEMA public TO :"app_user";
GRANT ALL PRIVILEGES ON SCHEMA public TO :"admin_user";

-- 7. Default privileges: objetos criados por forja_admin ficam acessiveis ao
--    runtime em DML apenas (sem DDL, sem TRUNCATE, sem ownership).
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";

--    Sequences: nextval (USAGE) e currval (SELECT) bastam ao runtime.
--    UPDATE (setval) NAO e concedido.
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";

--    Funcoes: por padrao PUBLIC recebe EXECUTE; revogamos e concedemos
--    explicitamente apenas ao runtime.
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO :"app_user";

-- -----------------------------------------------------------------------------
-- NOTA DE PRODUCAO:
-- Em ambiente produtivo, todas as senhas (bootstrap, admin, app) devem ser
-- injetadas exclusivamente via secrets gerenciados (ex: AWS Secrets Manager /
-- Vault / Kubernetes Secrets) e nunca versionadas em texto plano.
-- -----------------------------------------------------------------------------
