"""Adiciona translated_at às traduções de produto (migration 0018).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-13

A coluna `translated_at` registra quando a tradução foi gerada/atualizada.
Útil para auditoria e ordenação de retraduções pendentes.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_translations",
        sa.Column(
            "translated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("product_translations", "translated_at")
