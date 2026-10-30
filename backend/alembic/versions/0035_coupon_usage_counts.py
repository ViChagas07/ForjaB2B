"""Contagem global de usos do cupom para o checkout (SECURITY DEFINER).

``coupon_redemptions`` tem FORCE RLS por empresa. O checkout precisa contar os
usos APPLIED de TODAS as empresas para aplicar ``usage_limit_total`` sem expor
linhas de outros tenants. A funcao abaixo roda como ``forja_admin`` (que tem
policy de leitura administrativa criada em 0034) e devolve somente dois
agregados; ``forja_app`` recebe apenas EXECUTE.

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.coupon_usage_counts(
            p_coupon_id UUID,
            p_company_id UUID
        )
        RETURNS TABLE(total_uses BIGINT, company_uses BIGINT)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT
                count(*) FILTER (WHERE status = 'APPLIED')::bigint AS total_uses,
                count(*) FILTER (
                    WHERE status = 'APPLIED' AND company_id = p_company_id
                )::bigint AS company_uses
            FROM public.coupon_redemptions
            WHERE coupon_id = p_coupon_id;
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.coupon_usage_counts(UUID, UUID) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.coupon_usage_counts(UUID, UUID) TO forja_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app.coupon_usage_counts(UUID, UUID)")
