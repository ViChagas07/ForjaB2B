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


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
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
        sa.Column(
            "avatar_key",
            sa.Uuid(),
            nullable=True,
        ),
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
        sa.UniqueConstraint(
            "user_id", name="uq_user_preferences_user_id"
        ),
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


def downgrade() -> None:
    op.drop_table("user_preferences")