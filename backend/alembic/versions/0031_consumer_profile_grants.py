"""Garante grants do runtime em ``consumer_profiles`` (migration 0031).

Em bancos gerenciados, o bootstrap de roles/ACLs pode ter sido aplicado antes
de ``consumer_profiles`` existir. O Alembic cria a tabela como ``forja_admin``;
sem o grant explícito, a role de runtime (``forja_app``) recebe ``permission
denied`` na primeira tentativa de cadastro. O bloco abaixo e idempotente e
tolerante a ambientes que usam outro nome de role (nesses casos, o default
privilege do bootstrap continua valendo).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forja_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON public.consumer_profiles
                    TO forja_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forja_app') THEN
                REVOKE SELECT, INSERT, UPDATE, DELETE
                    ON public.consumer_profiles
                    FROM forja_app;
            END IF;
        END
        $$;
        """
    )
