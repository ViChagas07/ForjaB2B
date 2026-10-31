"""Adiciona contas de consumidor (CPF) na raiz do tenant (migration 0030).

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-29

Mudancas:
- ``companies.account_type`` (``COMPANY`` | ``PERSON``); contas pessoais nao
  possuem CNPJ (coluna passa a aceitar NULL) e ja nascem ``ACTIVE``;
- ``consumer_profiles`` (data de nascimento, genero e CEP), tenant-scoped com
  RLS, no mesmo padrao das demais tabelas de dominio.

A funcao ``app.resolve_user_by_email`` permanece com o retorno minimo de 4
colunas: o ``account_type`` e lido pela aplicacao depois de estabelecer o
contexto do tenant resolvido (``app.set_tenant_context``), sem ampliar o
bypass de RLS da role ``forja_auth``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_rls(table: str) -> None:
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


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "account_type",
            sa.String(24),
            nullable=False,
            server_default=sa.text("'COMPANY'"),
        ),
    )
    op.alter_column("companies", "cnpj", existing_type=sa.String(14), nullable=True)
    op.create_check_constraint(
        "account_type",
        "companies",
        "account_type IN ('COMPANY', 'PERSON')",
    )
    op.create_check_constraint(
        "account_type_cnpj",
        "companies",
        "(account_type = 'COMPANY' AND cnpj IS NOT NULL) "
        "OR (account_type = 'PERSON' AND cnpj IS NULL)",
    )

    op.create_table(
        "consumer_profiles",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(24), nullable=False),
        sa.Column("postal_code", sa.String(8), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_consumer_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "gender IN ('FEMININO', 'MASCULINO', 'NAO_BINARIO', 'OUTRO', "
            "'PREFIRO_NAO_INFORMAR')",
            name="gender",
        ),
        sa.CheckConstraint("postal_code ~ '^[0-9]{8}$'", name="postal_code_format"),
    )
    op.create_index("ix_consumer_profiles_company_id", "consumer_profiles", ["company_id"])
    _tenant_rls("consumer_profiles")


def downgrade() -> None:
    # Se existirem contas pessoais, o downgrade nao e seguro (a coluna CNPJ
    # voltaria a ser obrigatoria). O ALTER falha e a transacao inteira reverte.
    op.alter_column("companies", "cnpj", existing_type=sa.String(14), nullable=False)
    op.drop_table("consumer_profiles")
    op.drop_constraint("account_type_cnpj", "companies", type_="check")
    op.drop_constraint("account_type", "companies", type_="check")
    op.drop_column("companies", "account_type")
