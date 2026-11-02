"""Snapshot do desconto automatico CNPJ em tabela nova (sem ALTER/FK em tabelas existentes).

Em producao a role de migrations nao e owner de ``order_items`` nem tem
REFERENCES nela; portanto ``ALTER TABLE ... ADD COLUMN`` e ``CREATE TABLE ...
REFERENCES order_items`` falham. O snapshot vai para ``order_item_pricing``,
criada pela propria role de migrations, apenas com PK ``order_item_id`` (mesmo
tipo/UUID de ``order_items.id``) e colunas nullable. Nao ha FK para tabela
existente: a integridade e garantida pelo codigo, que grava a linha na mesma
transacao do item e le com LEFT JOIN.

Pedidos antigos simplesmente nao tem linha em ``order_item_pricing``; o
repositorio trata a ausencia como "sem snapshot". Nenhum dado e apagado.

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

_TABLE = "order_item_pricing"


def _tenant_visible() -> str:
    """Expressao de tenant para a policy (o item pertence a um pedido da empresa)."""
    return (
        "EXISTS (SELECT 1 FROM order_items oi "
        "JOIN orders o ON o.id = oi.order_id "
        f"WHERE oi.id = {_TABLE}.order_item_id "
        "AND o.company_id = app.current_company_id())"
    )


def upgrade() -> None:
    # Somente CREATE TABLE/INDEX e DDL na tabela NOVA. Nenhum ALTER em tabela
    # existente: a role de migrations e owner desta tabela recem-criada.
    op.create_table(
        _TABLE,
        # Sem ForeignKey: a role de producao nao e owner nem tem REFERENCES em
        # order_items. O PK garante 1:1; a aplicacao grava/limpa na mesma
        # transacao e trata ausencia como "sem snapshot".
        sa.Column("order_item_id", sa.Uuid(), primary_key=True),
        sa.Column("list_unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("list_line_total", sa.Numeric(14, 2), nullable=True),
        sa.Column("cnpj_discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("cnpj_discount_band", sa.SmallInteger(), nullable=True),
        sa.Column("cnpj_discount_amount", sa.Numeric(14, 2), nullable=True),
    )

    # RLS: o snapshot acompanha a visibilidade do item/pedido. A role de
    # migrations e owner da tabela nova, entao pode habilitar/criar policies.
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    visible = _tenant_visible()
    op.execute(f"CREATE POLICY {_TABLE}_select ON {_TABLE} FOR SELECT USING ({visible})")
    op.execute(f"CREATE POLICY {_TABLE}_insert ON {_TABLE} FOR INSERT WITH CHECK ({visible})")
    op.execute(
        f"CREATE POLICY {_TABLE}_update ON {_TABLE} FOR UPDATE "
        f"USING ({visible}) WITH CHECK ({visible})"
    )
    op.execute(f"CREATE POLICY {_TABLE}_delete ON {_TABLE} FOR DELETE USING ({visible})")

    # Garante DML ao runtime mesmo quando a role de migrations nao tem default
    # privileges (cenario do Render). A tabela e nova e pertence a esta role.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'forja_app') THEN
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE
                         ON order_item_pricing TO forja_app';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # DROP TABLE remove a tabela, policies, grants e o indice da PK. Nenhum
    # dado de order_items/orders e tocado.
    op.drop_table(_TABLE)
