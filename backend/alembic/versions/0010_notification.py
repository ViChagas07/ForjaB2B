"""Cria outbox de notificacoes e preferencias (migration 0010).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-09

``notifications`` e a outbox transacional de notificacoes (tenant-scoped). O
worker despacha por tenant; a enumeracao cross-tenant usa a funcao SECURITY
DEFINER ``app.list_due_notifications`` (owner ``forja_notification``), que le
``notifications`` sem contexto de tenant via policy dedicada (mesmo padrao do
``app.resolve_user_by_email`` (migration 0006). ``notification_preferences``
registra opt-out por usuario/canal.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOTIFICATION_ROLE = "forja_notification"


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
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("channel", sa.String(24), nullable=False, server_default=sa.text("'EMAIL'")),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('PENDING', 'SENT', 'FAILED', 'DEAD_LETTERED', 'SKIPPED')",
            name="status",
        ),
        sa.CheckConstraint("channel IN ('EMAIL')", name="channel"),
    )
    op.create_index("ix_notifications_company_id", "notifications", ["company_id"])
    op.create_index("ix_notifications_aggregate_id", "notifications", ["aggregate_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.CheckConstraint("channel IN ('EMAIL')", name="channel"),
    )
    op.create_index(
        "ix_notification_preferences_company_id", "notification_preferences", ["company_id"]
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])
    op.create_index(
        "uq_notification_preferences_scope",
        "notification_preferences",
        ["company_id", "user_id", "channel"],
        unique=True,
    )

    _tenant_rls("notifications")
    _tenant_rls("notification_preferences")

    # Policy dedicada para o worker (SECURITY DEFINER app.list_due_notifications):
    # forja_notification le notifications sem contexto de tenant, estritamente
    # para enumerar pendentes. Nao e um bypass generico (role NOLOGIN, unico
    # objeto que roda como ela e a funcao).
    op.execute(f"GRANT SELECT ON notifications TO {_NOTIFICATION_ROLE}")
    op.execute(
        f"CREATE POLICY notifications_dispatch ON notifications FOR SELECT "
        f"TO {_NOTIFICATION_ROLE} USING (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notifications_dispatch ON notifications")
    op.execute(f"REVOKE SELECT ON notifications FROM {_NOTIFICATION_ROLE}")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
