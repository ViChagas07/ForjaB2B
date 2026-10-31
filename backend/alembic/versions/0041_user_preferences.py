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
from sqlalchemy import text

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
    has_created_at = _column_exists(conn, "users", "created_at")
    has_updated_at = _column_exists(conn, "users", "updated_at")

    if any([has_display_currency, has_hide_spending, has_avatar, has_whatsapp]):
        # Mapeamento estruturado: (coluna_destino, expressao_origem_ou_default)
        # Isso garante que destino e origem sempre tenham o mesmo numero de itens
        column_mapping = [
            ("user_id", "u.id"),
            ("company_id", "u.company_id"),
            ("display_currency", "u.display_currency" if has_display_currency else "'BRL'::varchar(3)"),
            ("hide_spending", "u.hide_spending" if has_hide_spending else "false"),
            ("avatar_key", "u.avatar_key" if has_avatar else "NULL::uuid"),
            ("avatar_content_type", "u.avatar_content_type" if has_avatar else "NULL::varchar(32)"),
            ("avatar_data", "u.avatar_data" if has_avatar else "NULL::bytea"),
            ("avatar_updated_at", "u.avatar_updated_at" if has_avatar else "NULL::timestamptz"),
            ("whatsapp_phone", "u.whatsapp_phone" if has_whatsapp else "NULL::varchar(20)"),
            ("whatsapp_opt_in", "u.whatsapp_opt_in" if has_whatsapp else "false"),
            ("whatsapp_opt_in_at", "u.whatsapp_opt_in_at" if has_whatsapp else "NULL::timestamptz"),
            ("created_at", "COALESCE(u.created_at, now())" if has_created_at else "now()"),
            ("updated_at", "COALESCE(u.updated_at, now())" if has_updated_at else "now()"),
        ]

        if any([has_display_currency, has_hide_spending, has_avatar, has_whatsapp]):
            select_cols = [f"{expr} AS {col}" for col, expr in column_mapping]
            select_sql = f"SELECT {', '.join(select_cols)} FROM users u"
            target_cols = [col for col, _ in column_mapping]
            insert_sql = f"""
                INSERT INTO user_preferences (
                    {', '.join(target_cols)}
                )
                {select_sql}
                ON CONFLICT (user_id) DO NOTHING
            """
            conn.execute(text(insert_sql))


def downgrade() -> None:
    op.drop_table("user_preferences")


