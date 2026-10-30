"""Remove check invalido de desconto de frete.

``shipping_total`` guarda o frete LIQUIDO (depois de recovery e cupom). O check
``shipping_discount_amount <= shipping_total`` da 0033 impedia cupons SHIPPING
de 100% (ex.: frete 25, desconto 25, liquido 0). O limite superior correto ja
e garantido no dominio e pelos checks de nao-negatividade; o valor bruto do
frete nao e persistido.

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("shipping_discount_within_shipping", "orders", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "shipping_discount_within_shipping",
        "orders",
        "shipping_discount_amount <= shipping_total",
    )
