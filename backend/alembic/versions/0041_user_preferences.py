"""Tabela de preferencias do usuario (Fase 2).

Armazena preferencias que antes ficavam em colunas da tabela `users` e que
nao podem ser adicionadas la por falta de ownership em producao.
Esta tabela e nova, entao o role `forja` tem permissao total (CREATE TABLE).

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(conn, table: str, column: str, schema: str = "public") -> bool:
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    ).scalar()
    return bool(result)


def upgrade() -> None:
    conn = op.get_bind()

    # Cria a tabela user_preferences (nova, sem FK para users)
    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            sa.Uuid(),
            primary_key=True,
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column(
            "display_currency",
            sa.String(3),
            nullable=False,
            default="BRL",
            server_default=sa.text("'BRL'"),
        ),
        sa.Column(
            "hide_spending",
            sa.Boolean(),
            nullable=False,
            default=False,
            server_default=sa.text("false"),
        ),
        sa.Column("avatar_key", sa.Uuid(), nullable=True),
        sa.Column("avatar_content_type", sa.String(32), nullable=True),
        sa.Column("avatar_data", sa.LargeBinary(), nullable=True),
        sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("whatsapp_phone", sa.String(20), nullable=True),
        sa.Column(
            "whatsapp_opt_in",
            sa.Boolean(),
            nullable=False,
            default=False,
            server_default=sa.text("false"),
        ),
        sa.Column("whatsapp_opt_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    # RLS por company_id (tenant isolation)
    op.execute("ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_preferences FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY user_preferences_select ON user_preferences "
        "FOR SELECT USING (company_id = app.current_company_id())"
    )
    op.execute(
        "CREATE POLICY user_preferences_insert ON user_preferences "
        "FOR INSERT WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        "CREATE POLICY user_preferences_update ON user_preferences "
        "FOR UPDATE USING (company_id = app.current_company_id()) "
        "WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        "CREATE POLICY user_preferences_delete ON user_preferences "
        "FOR DELETE USING (company_id = app.current_company_id())"
    )

    # Migra dados de users para user_preferences se as colunas existirem
    # (ambientes que aplicaram 0037-0040 antes do fix de ownership)
    has_display_currency = _column_exists(conn, "users", "display_currency")
    has_hide_spending = _column_exists(conn, "users", "hide_spending")
    has_avatar = _column_exists(conn, "users", "avatar_key")
    has_whatsapp = _column_exists(conn, "users", "whatsapp_phone")

    if any([has_display_currency, has_hide_spending, has_avatar, has_whatsapp]):
        select_cols = ["u.id AS user_id", "u.company_id"]
        if has_display_currency:
            select_cols.append("u.display_currency")
        else:
            select_cols.append("'BRL'::varchar(3) AS display_currency")
        if has_hide_spending:
            select_cols.append("u.hide_spending")
        else:
            select_cols.append("false AS hide_spending")
        if has_avatar:
            select_cols.extend([
                "u.avatar_key",
                "u.avatar_content_type",
                "u.avatar_data",
                "u.avatar_updated_at",
            ])
        else:
            select_cols.extend([
                "NULL::uuid AS avatar_key",
                "NULL::varchar(32) AS avatar_content_type",
                "NULL::bytea AS avatar_data",
                "NULL::timestamptz AS avatar_updated_at",
            ])
        if has_whatsapp:
            select_cols.extend(["u.whatsapp_phone", "u.whatsapp_opt_in", "u.whatsapp_opt_in_at"])
        else:
            select_cols.extend([
                "NULL::varchar(20) AS whatsapp_phone",
                "false AS whatsapp_opt_in",
                "NULL::timestamptz AS whatsapp_opt_in_at",
            ])

        select_sql = f"SELECT {', '.join(select_cols)} FROM users u"
        insert_sql = f"""
            INSERT INTO user_preferences (
                user_id, company_id, display_currency, hide_spending,
                avatar_key, avatar_content_type, avatar_data, avatar_updated_at,
                whatsapp_phone, whatsapp_opt_in, whatsapp_opt_in_at,
                created_at, updated_at
            )
            {select_sql}
            ON CONFLICT (user_id) DO NOTHING
        """
        conn.execute(text(insert_sql))


def downgrade() -> None:
    op.drop_table("user_preferences")


from sqlalchemy import text