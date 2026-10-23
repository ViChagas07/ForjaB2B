"""Escopa as chaves de idempotencia de pedido/pagamento por empresa (0022).

Os indices unicos parciais de ``orders`` e ``payments`` eram globais, o que
fazia a mesma chave enviada por outra empresa colidir (ou vazar a existencia
de um pedido de outro tenant). A correcao inclui ``company_id`` no indice,
alinhando a idempotencia de negocio ao isolamento multi-tenant e a tabela
``idempotency_keys``.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_orders_idempotency_key", table_name="orders")
    op.create_index(
        "uq_orders_idempotency_key",
        "orders",
        ["company_id", "idempotency_key"],
        unique=True,
        postgresql_where="idempotency_key IS NOT NULL",
    )

    op.drop_index("uq_payments_idempotency_key", table_name="payments")
    op.create_index(
        "uq_payments_idempotency_key",
        "payments",
        ["company_id", "idempotency_key"],
        unique=True,
        postgresql_where="idempotency_key IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_payments_idempotency_key", table_name="payments")
    op.create_index(
        "uq_payments_idempotency_key",
        "payments",
        ["idempotency_key"],
        unique=True,
        postgresql_where="idempotency_key IS NOT NULL",
    )

    op.drop_index("uq_orders_idempotency_key", table_name="orders")
    op.create_index(
        "uq_orders_idempotency_key",
        "orders",
        ["idempotency_key"],
        unique=True,
        postgresql_where="idempotency_key IS NOT NULL",
    )
