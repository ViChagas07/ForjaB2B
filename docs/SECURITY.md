# Forja B2B — Segurança do Backend

## Credenciais e segredos

- Nenhum segredo real versionado. Todos os valores são defaults de dev
  (`.env.example`), injetados por variáveis de ambiente.
- `DATABASE_ADMIN_URL` existe **somente** para migrações (container one-off,
  `make migrate`); nunca é injetada nos containers de runtime.
- Roles PostgreSQL com menor privilégio: `forja_app` (DML, `NOBYPASSRLS`),
  `forja_admin` (DDL, `NOSUPERUSER`, `NOBYPASSRLS`), `forja_auth` e
  `forja_notification` (`NOLOGIN`, donas de funções `SECURITY DEFINER`).

## Autenticação e autorização

- JWT de acesso (HS256, curta duração) + refresh token com rotação (Redis).
- RBAC por papel (`ADMIN`, `BUYER`, `APPROVER`, `FINANCE`) no backend
  (`require_role`/`require_any_role`).
- OAuth Google: redirect tradicional, `state` anti-CSRF, exchange code de **uso
  único** (nunca tokens em URL).
- Webhook de pagamento: autenticado por assinatura HMAC-SHA256 do corpo
  (segredo compartilhado); o `company_id` vem dentro do payload assinado.

## Isolamento multi-tenant

- RLS (`FORCE ROW LEVEL SECURITY`) em todas as tabelas de domínio; contexto de
  tenant transacional, sem vazamento entre requests.
- Concorrência financeira serializada por `SELECT ... FOR UPDATE` na conta de
  crédito (impede captura/liberação duplicada).

## Prevenção de exposição

- Erros RFC 7807 sem stack trace nem dados internos.
- Logs estruturados sem senhas/tokens/authorization codes/PII.
- Sem tokens de sessão em URLs; sem segredos no frontend.

## Pendência conhecida

- **Rotação do segredo Google** anteriormente exposto: pendente do responsável no
  Google Cloud (não realizada nesta entrega).
