"""Adiciona a quantidade em estoque aos produtos do catalogo.

O catalogo passa a expor ``stock_quantity`` para a vitrine e para o formulario
administrativo. O backfill e deterministico (hash do SKU) e so atribui estoque
a produtos vendaveis: ativos e, quando EPI, com CA valido. Produtos
indisponiveis permanecem com zero unidades.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STOCK_RANGE = 50
_STOCK_LOTS_BASE = 5


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint("stock_quantity", "products", "stock_quantity >= 0")
    op.execute(
        sa.text(
            "UPDATE products SET stock_quantity = CASE "
            "WHEN status = 'ACTIVE' "
            "AND (is_epi = false OR (ca_valid_until IS NOT NULL "
            "AND ca_valid_until >= CURRENT_DATE)) "
            "THEN min_order_qty * ("
            f"{_STOCK_LOTS_BASE} + "
            f"(abs(hashtext(sku)::bigint) % {_STOCK_RANGE})"
            ")::int "
            "ELSE 0 END"
        )
    )


def downgrade() -> None:
    op.drop_constraint("stock_quantity", "products", type_="check")
    op.drop_column("products", "stock_quantity")
