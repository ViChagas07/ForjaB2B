"""Cria contas e ledger de credito (migration 0003).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07

``credit_accounts`` (uma por empresa) e ``credit_entries`` (ledger
append-only, sem ``updated_at``). O saldo disponivel deriva do somatorio do
ledger na Fase 2; nao ha coluna de saldo materializado.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
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
    op.create_table(
        "credit_accounts",
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
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
        sa.CheckConstraint("credit_limit >= 0", name="credit_limit"),
    )

    op.create_table(
        "credit_entries",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "credit_account_id",
            sa.Uuid(),
            sa.ForeignKey("credit_accounts.company_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entry_type", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "entry_type IN ('LIMIT_SET', 'RESERVE', 'RELEASE', 'INVOICE_CAPTURE', "
            "'PAYMENT', 'ADJUSTMENT')",
            name="entry_type",
        ),
    )
    op.create_index("ix_credit_entries_credit_account_id", "credit_entries", ["credit_account_id"])
    op.create_index("ix_credit_entries_company_id", "credit_entries", ["company_id"])
    op.create_index(
        "uq_credit_entries_idempotency_key",
        "credit_entries",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    _tenant_rls("credit_accounts")
    _tenant_rls("credit_entries")


def downgrade() -> None:
    op.drop_table("credit_entries")
    op.drop_table("credit_accounts")
