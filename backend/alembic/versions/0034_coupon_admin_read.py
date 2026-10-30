"""Permite leitura cross-tenant de resgates pela role administrativa.

A API admin precisa calcular usos totais e valor descontado de cada cupom.
Como ``coupon_redemptions`` tem FORCE RLS por ``company_id``, o owner
``forja_admin`` tambem estaria sujeito as policies de tenant. Esta policy
adicional e permissiva e libera SELECT para ``forja_admin``; a role de runtime
``forja_app`` continua restrita ao proprio tenant.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADMIN_ROLE = "forja_admin"
_POLICY = "coupon_redemptions_admin_read"


def upgrade() -> None:
    op.execute(
        f"CREATE POLICY {_POLICY} ON coupon_redemptions FOR SELECT TO {_ADMIN_ROLE} USING (true)"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {_POLICY} ON coupon_redemptions")
