"""Adiciona o status PAID ao pedido (migration 0020).

Pedidos pagos por cartao/PIX passam de ``RECEIVED``/``CREDIT_REVIEW`` para
``PAID`` quando o pagamento e confirmado (webhook Stripe ou webhook interno).
Boleto faturado continua em ``INVOICED`` ate a quitacao.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES_WITH_PAID = (
    "RECEIVED",
    "CREDIT_REVIEW",
    "PAID",
    "INVOICED",
    "IN_TRANSIT",
    "DELIVERED",
    "CANCELLED",
    "CREDIT_REJECTED",
)
_STATUSES_WITHOUT_PAID = tuple(status for status in _STATUSES_WITH_PAID if status != "PAID")


def _values(statuses: tuple[str, ...]) -> str:
    return ", ".join(f"'{status}'" for status in statuses)


def upgrade() -> None:
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_status")
    op.execute(
        "ALTER TABLE orders ADD CONSTRAINT ck_orders_status "
        f"CHECK (status IN ({_values(_STATUSES_WITH_PAID)}))"
    )


def downgrade() -> None:
    # A constraint antiga nao aceita PAID; normaliza antes de recriar. A tabela
    # tem RLS FORCE e a migration roda sem tenant, entao desabilita RLS apenas
    # durante o UPDATE e restaura em seguida.
    op.execute("ALTER TABLE orders NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders DISABLE ROW LEVEL SECURITY")
    op.execute("UPDATE orders SET status = 'RECEIVED' WHERE status = 'PAID'")
    op.execute("ALTER TABLE orders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_status")
    op.execute(
        "ALTER TABLE orders ADD CONSTRAINT ck_orders_status "
        f"CHECK (status IN ({_values(_STATUSES_WITHOUT_PAID)}))"
    )
