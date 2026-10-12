"""Cria as traducoes de produto (migration 0016).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-10

``product_translations`` guarda uma traducao por (produto, idioma) do nome,
descricao e valores de atributos de texto. Como o catalogo, e GLOBAL (sem RLS):
o runtime apenas le e a escrita ocorre pelo admin (chave de plataforma). O
``source_hash`` detecta mudanca na origem pt-BR (marca ``stale``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_translations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'machine'")),
        sa.Column("translated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("product_id", "locale", name="uq_product_translations_product_locale"),
        sa.CheckConstraint("status IN ('machine', 'reviewed', 'stale')", name="status"),
    )
    op.create_index("ix_product_translations_product_id", "product_translations", ["product_id"])


def downgrade() -> None:
    op.drop_table("product_translations")
