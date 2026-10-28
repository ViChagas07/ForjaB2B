"""Agente de recuperacao de carrinho: atividade, tentativas e ofertas (FASE 4).

1) ``carts.last_activity_at`` (timestamptz, indexada) — toda operacao de item
   (add/update/remove/clear) passa a atualiza-la na mesma transacao; backfill
   com ``updated_at``. O UPDATE de backfill roda com ``NO FORCE`` (owner
   temporariamente isento) porque a tabela tem FORCE RLS e a migration roda sem
   contexto de tenant.
2) ``cart_recovery_attempts`` — append-only, RLS de tenant no padrao do projeto.
3) ``cart_recovery_offers`` — ofertas de uso unico (frete gratis / 3%),
   RLS de tenant.
4) ``app.list_recovery_tenants`` — enumeracao cross-tenant de carrinhos
   elegiveis (24h..7d) para o worker, SECURITY DEFINER sobre a role NOLOGIN
   ``forja_recovery`` (mesmo padrao de app.list_due_notifications): leitura
   estritamente de ``carts`` via politica dedicada.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RECOVERY_ROLE = "forja_recovery"


def _tenant_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_select ON {table} "
        "FOR SELECT USING (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_insert ON {table} "
        "FOR INSERT WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_update ON {table} "
        "FOR UPDATE USING (company_id = app.current_company_id()) "
        "WITH CHECK (company_id = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_delete ON {table} "
        "FOR DELETE USING (company_id = app.current_company_id())"
    )


def upgrade() -> None:
    op.add_column("carts", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_carts_last_activity_at", "carts", ["last_activity_at"])
    # Backfill com updated_at (owner isento temporariamente do FORCE RLS).
    op.execute("ALTER TABLE carts NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "UPDATE carts SET last_activity_at = COALESCE(updated_at, created_at) "
        "WHERE last_activity_at IS NULL"
    )
    op.execute("ALTER TABLE carts FORCE ROW LEVEL SECURITY")

    op.create_table(
        "cart_recovery_offers",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "cart_id", sa.Uuid(), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("type IN ('FREE_SHIPPING', 'PERCENT_DISCOUNT')", name="type"),
    )
    op.create_index("ix_cart_recovery_offers_company_id", "cart_recovery_offers", ["company_id"])
    op.create_index("ix_cart_recovery_offers_cart_id", "cart_recovery_offers", ["cart_id"])

    op.create_table(
        "cart_recovery_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "cart_id", sa.Uuid(), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("chosen_action", sa.String(24), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default=sa.text("'EMAIL'")),
        sa.Column(
            "offer_id",
            sa.Uuid(),
            sa.ForeignKey("cart_recovery_offers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("guard_verdict", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "chosen_action IN ('REMIND', 'FREE_SHIPPING', 'DISCOUNT_3PCT', 'ESCALATE_HUMAN')",
            name="chosen_action",
        ),
        sa.CheckConstraint("status IN ('SENT', 'SKIPPED', 'FAILED')", name="status"),
        sa.CheckConstraint("channel IN ('EMAIL', 'WHATSAPP')", name="channel"),
        sa.CheckConstraint(
            "guard_verdict IS NULL OR guard_verdict IN ('ALLOW', 'BLOCK')", name="guard_verdict"
        ),
    )
    op.create_index("ix_cart_recovery_attempts_cart_id", "cart_recovery_attempts", ["cart_id"])
    op.create_index("ix_cart_recovery_attempts_company_id", "cart_recovery_attempts", ["company_id"])
    op.create_index("ix_cart_recovery_attempts_user_id", "cart_recovery_attempts", ["user_id"])
    op.create_index("ix_cart_recovery_attempts_offer_id", "cart_recovery_attempts", ["offer_id"])
    op.create_index("ix_cart_recovery_attempts_created_at", "cart_recovery_attempts", ["created_at"])

    _tenant_rls("cart_recovery_attempts")
    _tenant_rls("cart_recovery_offers")

    # Role dedicada do worker (NOLOGIN), criada no bootstrap
    # (docker/postgres/init-roles.sql, secao 4.7); a FUNCAO SECURITY DEFINER
    # app.list_recovery_tenants tambem vive no bootstrap (02-rls-setup.sql),
    # como app.list_due_notifications — ownership exige superusuario.
    op.execute(f"GRANT SELECT ON carts TO {_RECOVERY_ROLE}")
    op.execute(
        f"CREATE POLICY carts_recovery ON carts FOR SELECT TO {_RECOVERY_ROLE} USING (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS carts_recovery ON carts")
    op.execute(f"REVOKE SELECT ON carts FROM {_RECOVERY_ROLE}")
    op.drop_table("cart_recovery_attempts")
    op.drop_table("cart_recovery_offers")
    op.drop_index("ix_carts_last_activity_at", table_name="carts")
    op.drop_column("carts", "last_activity_at")
