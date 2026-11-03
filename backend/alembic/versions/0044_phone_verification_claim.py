"""Reivindicacao atomica de telefone verificado (Fase 5).

Cria uma funcao SECURITY DEFINER nova em ``public`` para trocar o vinculo de
um telefone entre tenants com uma unica transacao. A funcao serializa por
usuario e por telefone (advisory locks), remove o vinculo anterior e devolve
o dono antigo (sem e-mail/PII) para o fluxo enviar o aviso. Nao altera tabelas
pre-existentes: a unica tabela tocada e ``user_verified_phones``, criada pela
0043 e owned pela role de migrations.

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHONES = "user_verified_phones"
_AUTH_ROLE = "forja_auth"
_APP_ROLE = "forja_app"
_CLAIM = "public.claim_verified_phone"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_CLAIM}(
            p_phone TEXT,
            p_user_id UUID,
            p_company_id UUID
        )
        RETURNS TABLE(previous_user_id UUID, previous_company_id UUID)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            prev_user UUID;
            prev_company UUID;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtextextended(p_user_id::text, 0));
            PERFORM pg_advisory_xact_lock(hashtextextended(p_phone, 0));

            SELECT vp.user_id, vp.company_id
              INTO prev_user, prev_company
              FROM public.{_PHONES} AS vp
             WHERE vp.phone_e164 = p_phone
             LIMIT 1;

            IF prev_user IS NOT NULL AND prev_user = p_user_id THEN
                prev_user := NULL;
                prev_company := NULL;
            END IF;

            DELETE FROM public.{_PHONES}
             WHERE phone_e164 = p_phone OR user_id = p_user_id;

            INSERT INTO public.{_PHONES}
                (user_id, company_id, phone_e164, verified_at)
            VALUES
                (p_user_id, p_company_id, p_phone, now());

            RETURN QUERY SELECT prev_user, prev_company;
        END;
        $$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_CLAIM}(TEXT, UUID, UUID) FROM PUBLIC")

    # O owner da funcao precisa de DML e policy nas linhas de qualquer tenant;
    # forja_auth e NOLOGIN e so e alcancavel por funcoes SECURITY DEFINER.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_AUTH_ROLE}') THEN
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON {_PHONES} TO {_AUTH_ROLE}';
                EXECUTE 'CREATE POLICY {_PHONES}_auth_manage ON {_PHONES} '
                        'FOR ALL TO {_AUTH_ROLE} USING (true) WITH CHECK (true)';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION {_CLAIM}(TEXT, UUID, UUID) TO {_APP_ROLE}';
            END IF;
        END
        $$;
        """
    )

    # Ownership para forja_auth quando a role de migrations puder ceder; se
    # nao puder, a funcao fica com o owner atual e recebe policy total.
    op.execute(
        f"""
        DO $$
        DECLARE
            claim_owner TEXT := current_user;
            granted_create BOOLEAN := false;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_AUTH_ROLE}') THEN
                BEGIN
                    IF NOT has_schema_privilege('{_AUTH_ROLE}', 'public', 'CREATE') THEN
                        EXECUTE 'GRANT CREATE ON SCHEMA public TO {_AUTH_ROLE}';
                        granted_create := true;
                    END IF;
                    EXECUTE 'ALTER FUNCTION {_CLAIM}(TEXT, UUID, UUID) OWNER TO {_AUTH_ROLE}';
                    IF granted_create THEN
                        EXECUTE 'REVOKE CREATE ON SCHEMA public FROM {_AUTH_ROLE}';
                    END IF;
                    claim_owner := '{_AUTH_ROLE}';
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE WARNING
                        '0044: sem privilegio para transferir % para {_AUTH_ROLE}; owner %',
                        '{_CLAIM}', current_user;
                END;
            END IF;

            IF claim_owner <> '{_AUTH_ROLE}' THEN
                EXECUTE format(
                    'CREATE POLICY {_PHONES}_owner_manage ON {_PHONES} '
                    'FOR ALL TO %I USING (true) WITH CHECK (true)',
                    current_user
                );
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_CLAIM}(TEXT, UUID, UUID)")
    op.execute(f"DROP POLICY IF EXISTS {_PHONES}_auth_manage ON {_PHONES}")
    op.execute(f"DROP POLICY IF EXISTS {_PHONES}_owner_manage ON {_PHONES}")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_AUTH_ROLE}') THEN
                EXECUTE 'REVOKE SELECT, INSERT, UPDATE, DELETE ON {_PHONES} FROM {_AUTH_ROLE}';
            END IF;
        END
        $$;
        """
    )
