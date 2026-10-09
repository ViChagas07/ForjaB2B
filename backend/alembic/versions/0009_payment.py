"""Cria pagamentos e eventos de webhook (migration 0009).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-09

``payments`` registra a intencao de pagamento (PIX/CARD a vista ou BOLETO de
fatura) com maquina de estados. ``payment_events`` persiste eventos de webhook
de forma idempotente (unico por provider/event_id). Ambas tenant-scoped com RLS.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
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
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("method", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "discount_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'FAILED', 'CANCELLED', 'REFUNDED')",
            name="status",
        ),
        sa.CheckConstraint("method IN ('PIX', 'CARD', 'BOLETO')", name="method"),
        sa.CheckConstraint("amount >= 0", name="amount"),
        sa.CheckConstraint("discount_amount >= 0", name="discount_amount"),
    )
    op.create_index("ix_payments_company_id", "payments", ["company_id"])
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index(
        "uq_payments_provider_reference", "payments", ["provider_reference"], unique=True
    )
    op.create_index(
        "uq_payments_idempotency_key",
        "payments",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.Uuid(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
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
        sa.CheckConstraint("outcome IN ('APPLIED', 'DUPLICATE', 'REJECTED')", name="outcome"),
    )
    op.create_index("ix_payment_events_company_id", "payment_events", ["company_id"])
    op.create_index("ix_payment_events_payment_id", "payment_events", ["payment_id"])
    op.create_index(
        "uq_payment_events_provider_event", "payment_events", ["provider", "event_id"], unique=True
    )

    _tenant_rls("payments")
    _tenant_rls("payment_events")


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_table("payments")
