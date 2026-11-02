"""Snapshot do desconto automatico CNPJ nos itens do pedido.

Adiciona colunas nullable em ``order_items`` para preservar o calculo aplicado
no momento da compra: preco de tabela (antes do CNPJ), percentual, faixa
(15/30) e o preco final continua em ``unit_price``. Pedidos antigos ficam com
NULL (sem desconto CNPJ registrado) e nao sao alterados. Nenhum dado e apagado.

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("list_unit_price", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column("cnpj_discount_percent", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column("cnpj_discount_band", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_items", "cnpj_discount_band")
    op.drop_column("order_items", "cnpj_discount_percent")
    op.drop_column("order_items", "list_unit_price")
