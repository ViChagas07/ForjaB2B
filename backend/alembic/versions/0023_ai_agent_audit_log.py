"""Cria agent_audit_log (auditoria de agentes de IA) - Fase 12, passo 6.

`agent_audit_log` e append-only: registra eventos dos agentes de IA
(recuperacao de carrinho, chat) para observabilidade e investigacao.
TENANT-SCOPED quando `company_id` e informado (mesmo padrao RLS das demais
tabelas de tenant); linhas de chat de VISITANTE tem `company_id` NULL e a
policy de INSERT as aceita, mas nenhum tenant as ve (SELECT/UPDATE/DELETE
exigem igualdade exata com o tenant corrente).

Privacidade por construcao: `payload` guarda apenas hash sha256 do texto,
tamanho em caracteres e os primeiros 80 caracteres sanitizados (ver
`app.modules.ai.domain.audit_payload`) — nunca o texto completo do usuario
nem PII (CNPJ, e-mail, telefone).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_rls_with_anonymous_insert(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    # SELECT/UPDATE/DELETE: igualdade exata — linhas com company_id NULL
    # (visitante) ficam invisiveis para qualquer tenant.
    op.execute(
        f"CREATE POLICY {table}_select ON {table} "
        "FOR SELECT USING (company_id = app.current_company_id())"
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
    # INSERT: evento de tenant autenticado OU de visitante (company_id NULL).
    op.execute(
        f"CREATE POLICY {table}_insert ON {table} FOR INSERT "
        "WITH CHECK (company_id IS NULL OR company_id = app.current_company_id())"
    )


def upgrade() -> None:
    op.create_table(
        "agent_audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent", sa.String(16), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("verdict", sa.String(24), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("agent IN ('cart', 'chat')", name="agent"),
        sa.CheckConstraint("verdict IS NULL OR verdict IN ('ALLOW', 'BLOCK')", name="verdict"),
    )
    op.create_index("ix_agent_audit_log_company_id", "agent_audit_log", ["company_id"])
    op.create_index("ix_agent_audit_log_conversation_id", "agent_audit_log", ["conversation_id"])
    op.create_index("ix_agent_audit_log_created_at", "agent_audit_log", ["created_at"])

    _tenant_rls_with_anonymous_insert("agent_audit_log")


def downgrade() -> None:
    op.drop_table("agent_audit_log")
