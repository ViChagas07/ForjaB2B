-- -----------------------------------------------------------------------------
-- Forja B2B: Funcoes utilitarias de Row Level Security (RLS) e contexto tenant
-- -----------------------------------------------------------------------------
-- Executado SOMENTE via 02-rls-setup.sh no bootstrap do initdb, conectando como
-- forja_admin (owner do database) para que o schema e as funcoes fiquem owned
-- pela role administrativa restrita, e nao pelo superuser de bootstrap.
--
-- Fornece (schema "app", namespace de GUCs "forja.*"):
--   1. app.current_company_id(): le forja.current_company_id da sessao
--   2. app.current_user_id(): le forja.current_user_id da sessao
--   3. app.set_tenant_context(company_id, user_id): define o contexto LOCAL
--      da transacao corrente (set_config(..., is_local = true))
--
-- ATENCAO: app.set_tenant_context NAO autentica nem autoriza o usuario.
-- O backend DEVE derivar company_id/user_id de uma identidade autenticada e
-- autorizada antes de definir o contexto, sempre na mesma transacao das
-- consultas protegidas por RLS.
-- -----------------------------------------------------------------------------

\if :{?app_user}
\else
    \echo 'FATAL: variavel psql app_user ausente. Execute via 02-rls-setup.sh.'
    \quit 1
\endif
\if :{?admin_user}
\else
    \echo 'FATAL: variavel psql admin_user ausente. Execute via 02-rls-setup.sh.'
    \quit 1
\endif

-- Schema "app" para funcoes de suporte; owned pela role administrativa restrita.
CREATE SCHEMA IF NOT EXISTS app;
ALTER SCHEMA app OWNER TO :"admin_user";
REVOKE ALL ON SCHEMA app FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO :"app_user";
-- forja_auth precisa de USAGE + CREATE no schema app para assumir o ownership
-- da funcao app.resolve_user_by_email (SECURITY DEFINER). A role e NOLOGIN e
-- inalcancavel fora da funcao, portanto CREATE nao amplia a superficie real.
GRANT USAGE, CREATE ON SCHEMA app TO forja_auth;
-- forja_notification (despacho da outbox) segue o mesmo padrao.
GRANT USAGE, CREATE ON SCHEMA app TO forja_notification;

-- -----------------------------------------------------------------------------
-- 1. app.current_company_id(): UUID do tenant ativo ou NULL se ausente/invalido.
--    STABLE: consistente dentro da query e amigavel ao planner.
--    SECURITY INVOKER: executa com os privilegios de quem invoca.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.current_company_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
SECURITY INVOKER
AS $$
DECLARE
    v_val TEXT;
BEGIN
    v_val := current_setting('forja.current_company_id', true);
    IF v_val IS NULL OR v_val = '' THEN
        RETURN NULL;
    END IF;
    RETURN v_val::UUID;
EXCEPTION
    WHEN invalid_text_representation THEN
        RETURN NULL;
END;
$$;

COMMENT ON FUNCTION app.current_company_id() IS
    'Retorna o UUID do company_id configurado na sessao (forja.current_company_id) ou NULL se ausente/invalido.';

-- -----------------------------------------------------------------------------
-- 2. app.current_user_id(): UUID do usuario ativo ou NULL se ausente/invalido.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.current_user_id()
RETURNS UUID
LANGUAGE plpgsql
STABLE
PARALLEL SAFE
SECURITY INVOKER
AS $$
DECLARE
    v_val TEXT;
BEGIN
    v_val := current_setting('forja.current_user_id', true);
    IF v_val IS NULL OR v_val = '' THEN
        RETURN NULL;
    END IF;
    RETURN v_val::UUID;
EXCEPTION
    WHEN invalid_text_representation THEN
        RETURN NULL;
END;
$$;

COMMENT ON FUNCTION app.current_user_id() IS
    'Retorna o UUID do user_id configurado na sessao (forja.current_user_id) ou NULL se ausente/invalido.';

-- -----------------------------------------------------------------------------
-- 3. app.set_tenant_context(company_id, user_id): contexto LOCAL da transacao.
--    Deve ser chamado na mesma transacao das consultas protegidas. Em
--    autocommit, uma chamada isolada NAO estabelece contexto para a proxima
--    consulta. Esta funcao NAO autentica nem autoriza o usuario.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.set_tenant_context(p_company_id UUID, p_user_id UUID DEFAULT NULL)
RETURNS VOID
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
AS $$
BEGIN
    PERFORM set_config('forja.current_company_id', COALESCE(p_company_id::TEXT, ''), true);
    IF p_user_id IS NOT NULL THEN
        PERFORM set_config('forja.current_user_id', p_user_id::TEXT, true);
    ELSE
        PERFORM set_config('forja.current_user_id', '', true);
    END IF;
END;
$$;

COMMENT ON FUNCTION app.set_tenant_context(UUID, UUID) IS
    'Define forja.current_company_id e forja.current_user_id para a transacao corrente (is_local = true). Nao autentica nem autoriza.';

-- -----------------------------------------------------------------------------
-- 4. app.resolve_user_by_email(p_email): resolucao de identidade NO LOGIN.
--    SECURITY DEFINER (owner: forja_auth, NOLOGIN) porque a tabela public.users
--    tem FORCE RLS: antes de conhecer o tenant a aplicacao nao consegue ler a
--    propria linha do usuario pela policy padrao (company_id = current_company).
--    A funcao retorna APENAS o minimo necessario ao login (id, company_id,
--    status e password_hash) de UM unico email, sem aceitar SQL arbitario
--    (p_email e parametro tipado). NAO e um mecanismo generico de bypass de
--    RLS: a leitura ampla e limitada a role forja_auth por politica dedicada
--    (migration 0006), e forja_auth e inalcancavel fora desta funcao.
--    search_path fixo previne hijack por objetos de esquemas nao qualificados.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.resolve_user_by_email(p_email TEXT)
RETURNS TABLE(user_id UUID, company_id UUID, status TEXT, password_hash TEXT)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.company_id, u.status::TEXT, u.password_hash::TEXT
    FROM public.users u
    WHERE u.email = lower(trim(p_email))
    LIMIT 1;
END;
$$;

COMMENT ON FUNCTION app.resolve_user_by_email(TEXT) IS
    'Resolve (user_id, company_id, status, password_hash) por email para o login. SECURITY DEFINER sobre forja_auth; retorna apenas o minimo necessario.';

-- -----------------------------------------------------------------------------
-- 5. app.list_due_notifications(p_limit, p_max_attempts): enumeracao de
--    notificacoes pendentes para o worker (despacho da outbox).
--    SECURITY DEFINER (owner: forja_notification, NOLOGIN) porque a tabela
--    public.notifications tem FORCE RLS e o worker precisa enumerar pendentes
--    de TODOS os tenants antes de despachar cada uma no seu proprio contexto.
--    Retorna apenas (notification_id, company_id); nao e um mecanismo generico
--    de bypass de RLS (leitura limitada a role forja_notification por politica
--    dedicada na migration 0010). search_path fixo previne hijack.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app.list_due_notifications(p_limit INTEGER, p_max_attempts INTEGER)
RETURNS TABLE(notification_id UUID, company_id UUID)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    RETURN QUERY
    SELECT n.id, n.company_id
    FROM public.notifications n
    WHERE n.status = 'PENDING'
       OR (n.status = 'FAILED' AND n.attempts < p_max_attempts)
    ORDER BY n.created_at, n.id
    LIMIT p_limit;
END;
$$;

COMMENT ON FUNCTION app.list_due_notifications(INTEGER, INTEGER) IS
    'Enumera (notification_id, company_id) das notificacoes pendentes para o worker. SECURITY DEFINER sobre forja_notification.';

-- -----------------------------------------------------------------------------
-- Ownership e permissoes de execucao
-- -----------------------------------------------------------------------------
ALTER FUNCTION app.current_company_id() OWNER TO :"admin_user";
ALTER FUNCTION app.current_user_id() OWNER TO :"admin_user";
ALTER FUNCTION app.set_tenant_context(UUID, UUID) OWNER TO :"admin_user";
-- A funcao de login e owned pela role dedicada forja_auth (SECURITY DEFINER).
ALTER FUNCTION app.resolve_user_by_email(TEXT) OWNER TO forja_auth;
-- A funcao de despacho e owned pela role dedicada forja_notification.
ALTER FUNCTION app.list_due_notifications(INTEGER, INTEGER) OWNER TO forja_notification;

-- Funcoes novas concedem EXECUTE a PUBLIC por padrao: revogar explicitamente.
REVOKE EXECUTE ON FUNCTION app.current_company_id() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.current_user_id() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.set_tenant_context(UUID, UUID) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.resolve_user_by_email(TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION app.list_due_notifications(INTEGER, INTEGER) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.current_company_id() TO :"app_user";
GRANT EXECUTE ON FUNCTION app.current_user_id() TO :"app_user";
GRANT EXECUTE ON FUNCTION app.set_tenant_context(UUID, UUID) TO :"app_user";
GRANT EXECUTE ON FUNCTION app.resolve_user_by_email(TEXT) TO :"app_user";
GRANT EXECUTE ON FUNCTION app.list_due_notifications(INTEGER, INTEGER) TO :"app_user";

-- Mesma politica para funcoes futuras do schema app criadas pelo admin.
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA app
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_user" IN SCHEMA app
    GRANT EXECUTE ON FUNCTIONS TO :"app_user";
