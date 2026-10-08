"""Habilita resolucao segura de identidade no login (migration 0006).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07

A tabela ``users`` tem FORCE RLS com policy ``company_id = app.current_company_id()``.
No login, antes de conhecer o tenant, a aplicacao nao consegue ler a linha do
usuario pela policy padrao. A decisao arquitetural (Fase 2) usa a funcao
``app.resolve_user_by_email`` (SECURITY DEFINER, owner ``forja_auth``, NOLOGIN)
para resolver email -> (user_id, company_id, status, password_hash).

Para a funcao conseguir ler ``users`` SEM contexto de tenant, concedemos a
``forja_auth`` (e somente a ela) uma policy de SELECT dedicada. Isso NAO e um
bypass generico: a role e inalcancavel por login (NOLOGIN), o unico objeto que
roda como ela e a funcao, e a funcao limita a leitura a um unico email com
apenas 4 colunas.

``forja_auth`` NAO tem BYPASSRLS (ver bootstrap init-roles.sql): o acesso se da
exclusivamente pela policy abaixo, com privilegio minimo (SELECT apenas).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTH_ROLE = "forja_auth"


def upgrade() -> None:
    # Privilegio minimo: somente leitura, somente na tabela de usuarios.
    op.execute(f"GRANT SELECT ON users TO {_AUTH_ROLE}")
    # Policy dedicada (permissive): forja_auth le users sem tenant context,
    # estritamente necessaria ao login. Outras roles continuam sob a policy
    # padrao (company_id = app.current_company_id()).
    op.execute(f"CREATE POLICY users_auth_lookup ON users FOR SELECT TO {_AUTH_ROLE} USING (true)")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_auth_lookup ON users")
    op.execute(f"REVOKE SELECT ON users FROM {_AUTH_ROLE}")
