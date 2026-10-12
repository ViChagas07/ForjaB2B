"""Cria as definicoes de atributos de produto (migration 0017).

``product_attribute_definitions`` armazena o schema dos atributos
opcionais de produto (modelo, cor, tamanho, etc.), com tipo, unidade,
opcoes de enum, escopo (global ou por categoria), secao e ordem de
exibicao. O runtime valida valores contra estas definicoes; a escrita
e restrita ao admin (chave de plataforma).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_attribute_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("options", JSONB(), nullable=True),
        sa.Column(
            "scope", JSONB(), nullable=False, server_default=sa.text("'[\"global\"]'::jsonb")
        ),
        sa.Column("section", sa.String(50), nullable=False, server_default=sa.text("'geral'")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("min_value", sa.Numeric(12, 3), nullable=True),
        sa.Column("max_value", sa.Numeric(12, 3), nullable=True),
        sa.Column("max_length", sa.Integer(), nullable=True),
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
            "type IN ('text', 'number', 'enum', 'boolean')",
            name="product_attribute_definitions_type_check",
        ),
    )
    op.create_index(
        "ix_product_attribute_definitions_key",
        "product_attribute_definitions",
        ["key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("product_attribute_definitions")
