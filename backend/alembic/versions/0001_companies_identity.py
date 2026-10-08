"""Cria empresas, enderecos, usuarios e vinculos (migration 0001).

Revision ID: 0001
Revises:
Create Date: 2026-10-07

Tabelas tenant-scoped com RLS (ENABLE + FORCE):
- ``companies`` usa ``id`` como chave de tenant (a propria raiz do tenant);
- ``company_addresses``, ``users`` e ``company_members`` usam ``company_id``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_rls(table: str, *, key: str = "company_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_select ON {table} "
        f"FOR SELECT USING ({key} = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_insert ON {table} "
        f"FOR INSERT WITH CHECK ({key} = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_update ON {table} "
        f"FOR UPDATE USING ({key} = app.current_company_id()) "
        f"WITH CHECK ({key} = app.current_company_id())"
    )
    op.execute(
        f"CREATE POLICY {table}_delete ON {table} "
        f"FOR DELETE USING ({key} = app.current_company_id())"
    )


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("trade_name", sa.String(200), nullable=True),
        sa.Column("state_registration", sa.String(20), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("cnpj", name="uq_companies_cnpj"),
        sa.CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="cnpj_format"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'REJECTED')",
            name="status",
        ),
    )

    op.create_table(
        "company_addresses",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "address_type", sa.String(24), nullable=False, server_default=sa.text("'SHIPPING'")
        ),
        sa.Column("street", sa.String(200), nullable=False),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("complement", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("postal_code", sa.String(8), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "address_type IN ('BILLING', 'SHIPPING')",
            name="address_type",
        ),
    )
    op.create_index("ix_company_addresses_company_id", "company_addresses", ["company_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("cpf_hash", sa.String(64), nullable=False),
        sa.Column("cpf_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default=sa.text("'PENDING_EMAIL'"),
        ),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("cpf_hash", name="uq_users_cpf_hash"),
        sa.CheckConstraint(
            "status IN ('PENDING_EMAIL', 'PENDING_APPROVAL', 'ACTIVE', 'SUSPENDED')",
            name="status",
        ),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])

    op.create_table(
        "company_members",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(24), nullable=False, server_default=sa.text("'BUYER'")),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_members_company_user"),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'BUYER', 'APPROVER', 'FINANCE')",
            name="role",
        ),
        sa.CheckConstraint(
            "status IN ('INVITED', 'ACTIVE', 'DISABLED')",
            name="status",
        ),
    )
    op.create_index("ix_company_members_company_id", "company_members", ["company_id"])
    op.create_index("ix_company_members_user_id", "company_members", ["user_id"])

    _tenant_rls("companies", key="id")
    _tenant_rls("company_addresses")
    _tenant_rls("users")
    _tenant_rls("company_members")


def downgrade() -> None:
    op.drop_table("company_members")
    op.drop_table("users")
    op.drop_table("company_addresses")
    op.drop_table("companies")
