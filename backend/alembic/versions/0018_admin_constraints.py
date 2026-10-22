"""Ajusta constraints de status de produto e unicidade da outbox (migration 0018).

Duas correcoes necessarias para o fluxo de administracao de catalogo:

1. ``products.status`` passa a aceitar ``DRAFT`` (usado ao despublicar um
   produto pelo backoffice). A constraint original aceitava apenas ``ACTIVE``
   e ``INACTIVE``.
2. ``search_outbox`` recebe a constraint de unicidade em
   ``(aggregate_id, event_type)``. O ``INSERT ... ON CONFLICT`` usado pelos
   eventos UPSERT/DELETE exige um indice/constraint unico correspondente.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_status")
    op.execute(
        "ALTER TABLE products ADD CONSTRAINT ck_products_status "
        "CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE'))"
    )
    op.execute(
        "ALTER TABLE search_outbox DROP CONSTRAINT IF EXISTS uq_search_outbox_aggregate_event"
    )
    op.execute(
        "ALTER TABLE search_outbox ADD CONSTRAINT uq_search_outbox_aggregate_event "
        "UNIQUE (aggregate_id, event_type)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE search_outbox DROP CONSTRAINT IF EXISTS uq_search_outbox_aggregate_event"
    )
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS ck_products_status")
    op.execute(
        "ALTER TABLE products ADD CONSTRAINT ck_products_status "
        "CHECK (status IN ('ACTIVE', 'INACTIVE'))"
    )
