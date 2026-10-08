"""Cria catalogo e pricing (migration 0002).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07

Tabelas GLOBAIS (catalogo da distribuidora, compartilhado entre tenants):
``categories``, ``brands``, ``products`` e ``product_price_tiers``. Nao tem
RLS nem ``company_id``. A escrita e revogada de ``forja_app`` (a role de
runtime so le o catalogo); apenas ``forja_admin`` escreve.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APP_ROLE = "forja_app"


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(150), nullable=False),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("name", name="uq_categories_name"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    op.create_table(
        "brands",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(150), nullable=False),
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
        sa.UniqueConstraint("name", name="uq_brands_name"),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            sa.Uuid(),
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("is_epi", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ca_number", sa.String(64), nullable=True),
        sa.Column("ca_valid_until", sa.Date(), nullable=True),
        sa.Column("ncm", sa.String(8), nullable=True),
        sa.Column("unit_of_measure", sa.String(10), nullable=True),
        sa.Column("weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("min_order_qty", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("base_unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
        sa.Column("attributes", JSONB(), nullable=True),
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
        sa.UniqueConstraint("sku", name="uq_products_sku"),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="status"),
        sa.CheckConstraint("min_order_qty >= 1", name="min_order_qty"),
        sa.CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="weight"),
        sa.CheckConstraint("base_unit_price >= 0", name="base_price"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_brand_id", "products", ["brand_id"])
    op.create_index(
        "ix_products_attributes_gin", "products", ["attributes"], postgresql_using="gin"
    )
    op.create_index(
        "ix_products_ca_valid_until",
        "products",
        ["ca_valid_until"],
        postgresql_where=sa.text("is_epi"),
    )

    op.create_table(
        "product_price_tiers",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("min_quantity", sa.Integer(), nullable=False),
        sa.Column("max_quantity", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'BRL'")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
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
            "product_id", "min_quantity", name="uq_product_price_tiers_product_min_qty"
        ),
        sa.CheckConstraint("min_quantity >= 1", name="min_qty"),
        sa.CheckConstraint(
            "max_quantity IS NULL OR max_quantity >= min_quantity",
            name="range",
        ),
        sa.CheckConstraint("unit_price > 0", name="unit_price"),
    )
    op.create_index("ix_product_price_tiers_product_id", "product_price_tiers", ["product_id"])

    # Catalogo global: somente leitura para a role de runtime.
    for table in ("categories", "brands", "products", "product_price_tiers"):
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {table} FROM {_APP_ROLE}")


def downgrade() -> None:
    op.drop_table("product_price_tiers")
    op.drop_table("products")
    op.drop_table("brands")
    op.drop_table("categories")
