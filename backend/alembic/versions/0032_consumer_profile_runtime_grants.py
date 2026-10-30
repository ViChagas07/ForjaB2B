"""Garante DML em ``consumer_profiles`` para a role real de runtime.

Em producao (Render) a aplicacao usa a role principal ``forja``; em
Compose/VPS usa ``forja_app``. A migration 0031 cobre ``forja_app``, mas a
tabela nova nao herda grants diretos de ``forja``. Sem este grant o cadastro
CPF falharia com ``permission denied`` depois da 0030.

O bloco e idempotente e tolerante a ambientes que nao possuem uma das roles.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            target_role TEXT;
        BEGIN
            FOREACH target_role IN ARRAY ARRAY['forja_app', 'forja']
            LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target_role) THEN
                    EXECUTE format(
                        'GRANT SELECT, INSERT, UPDATE, DELETE ON public.consumer_profiles TO %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            target_role TEXT;
        BEGIN
            FOREACH target_role IN ARRAY ARRAY['forja_app', 'forja']
            LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target_role) THEN
                    EXECUTE format(
                        'REVOKE SELECT, INSERT, UPDATE, DELETE ON public.consumer_profiles FROM %I',
                        target_role
                    );
                END IF;
            END LOOP;
        END
        $$;
        """
    )
