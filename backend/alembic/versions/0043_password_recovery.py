"""Recuperacao de conta: telefones verificados e estado de credenciais (Fase 1).

Cria duas tabelas novas, sem ALTER/DROP em tabelas existentes (a role de
migrations pode nao ser owner delas em producao):

- ``user_verified_phones``: telefone E.164 verificado, unico globalmente e
  unico por usuario, tenant-scoped por ``company_id``.
- ``user_credential_state``: estado 1:1 por usuario (epoch de credencial e
  data da ultima troca de senha).

Para o fluxo nao autenticado, a tabela de telefones tem FORCE RLS e uma policy
dedicada. A funcao nova ``public.resolve_user_by_verified_phone`` e SECURITY
DEFINER e retorna apenas ``user_id`` e ``company_id`` de um telefone exato; o
runtime continua sem SELECT direto na tabela. A checagem de conta ACTIVE e do
fluxo de envio, que roda depois de resolver o tenant, para nao expor status nao
autenticado.

A funcao fica no schema ``public`` (e nao em ``app``) porque a role de
migrations tem CREATE garantido em ``public`` pelo preflight, mas pode ter
apenas USAGE em ``app``; criar em ``app`` bloquearia o deploy nesse cenario.
A ownership vai para ``forja_auth`` quando a role existir, a role de migrations
puder conceder CREATE temporario em ``public`` e for membro de ``forja_auth``.
Caso contrario, a funcao permanece com a role de migrations e recebe uma policy
dedicada minima, mantendo o upgrade funcional sem ampliar o acesso do runtime.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHONES = "user_verified_phones"
_CREDENTIAL_STATE = "user_credential_state"
_AUTH_ROLE = "forja_auth"
_APP_ROLE = "forja_app"
_PHONE_LOOKUP = "public.resolve_user_by_verified_phone"


def _tenant_rls(table: str) -> None:
    """Habilita FORCE RLS e as policies de tenant para uma tabela nova."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_select ON {table} "
        "FOR SELECT USING (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_insert ON {table} "
        "FOR INSERT WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_update ON {table} "
        "FOR UPDATE USING (company_id = app.current_company_id()) "
        "WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_delete ON {table} "
        "FOR DELETE USING (company_id = app.current_company_id())"
    )


def _grant_dml(table: str) -> None:
    """Concede DML ao runtime quando a role existir (cenario do Render)."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {_APP_ROLE}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        _PHONES,
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", name=f"uq_{_PHONES}_user_id"),
        sa.UniqueConstraint("phone_e164", name=f"uq_{_PHONES}_phone_e164"),
    )

    op.create_table(
        _CREDENTIAL_STATE,
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column(
            "credential_epoch",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "credential_epoch >= 0",
            name="credential_epoch_non_negative",
        ),
    )

    _tenant_rls(_PHONES)
    _tenant_rls(_CREDENTIAL_STATE)
    _grant_dml(_PHONES)
    _grant_dml(_CREDENTIAL_STATE)

    # A funcao SECURITY DEFINER e criada pela role de migrations. Quando
    # possivel, a ownership passa para forja_auth (NOLOGIN), replicando a
    # migration 0006. O ALTER OWNER exige que o novo owner possa criar no
    # schema; concedemos CREATE em public apenas dentro desta transacao e o
    # revogamos em seguida. Sem essa permissao (ou sem membership), a funcao
    # continua com a role de migrations e recebe uma policy dedicada minima.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_PHONE_LOOKUP}(p_phone TEXT)
        RETURNS TABLE(user_id UUID, company_id UUID)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT vp.user_id, vp.company_id
            FROM public.{_PHONES} AS vp
            WHERE vp.phone_e164 = p_phone
        $$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {_PHONE_LOOKUP}(TEXT) FROM PUBLIC")
    # Concede EXECUTE ANTES da transferencia de ownership: depois que a funcao
    # passa a forja_auth, a role de migrations (NOINHERIT) deixa de ser owner
    # e nao teria GRANT OPTION para conceder ao runtime.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION {_PHONE_LOOKUP}(TEXT) TO {_APP_ROLE}';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        f"""
        DO $$
        DECLARE
            has_auth_role BOOLEAN := EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{_AUTH_ROLE}'
            );
            granted_create BOOLEAN := false;
            transfer_ok BOOLEAN := false;
        BEGIN
            IF has_auth_role THEN
                BEGIN
                    IF NOT has_schema_privilege('{_AUTH_ROLE}', 'public', 'CREATE') THEN
                        EXECUTE 'GRANT CREATE ON SCHEMA public TO {_AUTH_ROLE}';
                        granted_create := true;
                    END IF;
                    EXECUTE 'ALTER FUNCTION {_PHONE_LOOKUP}(TEXT) OWNER TO {_AUTH_ROLE}';
                    IF granted_create THEN
                        EXECUTE 'REVOKE CREATE ON SCHEMA public FROM {_AUTH_ROLE}';
                    END IF;
                    transfer_ok := true;
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE WARNING
                        '0043: sem privilegio para transferir % para {_AUTH_ROLE}; owner %',
                        '{_PHONE_LOOKUP}', current_user;
                END;
            END IF;

            IF transfer_ok THEN
                EXECUTE 'GRANT SELECT ON {_PHONES} TO {_AUTH_ROLE}';
                EXECUTE 'CREATE POLICY {_PHONES}_auth_lookup ON {_PHONES} '
                        'FOR SELECT TO {_AUTH_ROLE} USING (true)';
            ELSE
                EXECUTE format(
                    'CREATE POLICY {_PHONES}_owner_lookup ON {_PHONES} '
                    'FOR SELECT TO %I USING (true)',
                    current_user
                );
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {_PHONE_LOOKUP}(TEXT)")
    op.drop_table(_CREDENTIAL_STATE)
    op.drop_table(_PHONES)
