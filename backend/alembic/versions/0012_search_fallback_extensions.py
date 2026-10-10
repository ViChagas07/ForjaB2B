"""Extensoes e indices para busca textual de fallback no PostgreSQL.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-10

A busca lexical primaria e no Elasticsearch. Esta migration prepara o fallback
no PostgreSQL com `tsvector` na configuracao `portuguese`, `unaccent` e
`pg_trgm`. As extensoes sao do pacote `contrib` e devem estar disponiveis na
imagem oficial; em producao, verifique com o DBA/operador se elas estao
habilitadas antes de aplicar a migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "ix_products_search_text",
        "products",
        [sa.text("to_tsvector('portuguese', name || ' ' || COALESCE(description, ''))")],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_products_sku_trgm",
        "products",
        ["sku"],
        postgresql_using="gin",
        postgresql_ops={"sku": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_products_name_trgm",
        "products",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_products_name_trgm", table_name="products")
    op.drop_index("ix_products_sku_trgm", table_name="products")
    op.drop_index("ix_products_search_text", table_name="products")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
