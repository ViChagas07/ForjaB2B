"""Cria a outbox de sincronizacao do indice de busca (migration 0011).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-10

``search_outbox`` e a outbox transacional da sincronizacao do indice de busca.
Como o catalogo, e GLOBAL (sem RLS e sem ``company_id``). O evento e gravado na
mesma transacao da alteracao do produto e processado depois (Celery). Falhas
ficam registradas (status/attempts/last_error) e sao reprocessaveis; nada e
perdido. Ainda nao ha caminho de escrita de catalogo no runtime: a tabela ja
existe, pronta para o backoffice.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "aggregate_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'product'"),
        ),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint("event_type IN ('UPSERT', 'DELETE')", name="event_type"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'FAILED', 'DEAD_LETTERED')",
            name="status",
        ),
    )
    op.create_index("ix_search_outbox_status", "search_outbox", ["status"])
    op.create_index("ix_search_outbox_aggregate_id", "search_outbox", ["aggregate_id"])


def downgrade() -> None:
    op.drop_table("search_outbox")
