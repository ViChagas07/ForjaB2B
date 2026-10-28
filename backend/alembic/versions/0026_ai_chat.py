"""Chat de IA: conversas, mensagens e limpeza por TTL - FASE 5.

- `chat_conversations` (UUID nao adivinhavel; company/user nullable para
  visitante; expires_at) e `chat_messages` (role user|assistant, conteudo ja
  sanitizado), com RLS de tenant no padrao do projeto: linhas de VISITANTE
  (company NULL) visiveis apenas por quem conhece o UUID; conversa de usuario
  logado so pelo dono (checagem no servico) e pelo tenant.
- Role NOLOGIN `forja_chat` + funcao SECURITY DEFINER
  `app.delete_expired_chat_conversations` (criada no bootstrap, ownership
  exige superusuario) para a limpeza diaria.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHAT_ROLE = "forja_chat"


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("locale", sa.String(16), nullable=False, server_default=sa.text("'pt-BR'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_conversations_company_id", "chat_conversations", ["company_id"])
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"])
    op.create_index("ix_chat_conversations_expires_at", "chat_conversations", ["expires_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="role"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])

    # RLS de conversas: visitante (company NULL) acessivel por UUID; tenant so
    # ve as proprias. INSERT aceita NULL (visitante) ou o tenant corrente.
    op.execute("ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_conversations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chat_conversations_select ON chat_conversations FOR SELECT "
        "USING (company_id IS NULL OR company_id = app.current_company_id())"
    )
    op.execute(
        "CREATE POLICY chat_conversations_insert ON chat_conversations FOR INSERT "
        "WITH CHECK (company_id IS NULL OR company_id = app.current_company_id())"
    )
    op.execute(
        "CREATE POLICY chat_conversations_update ON chat_conversations FOR UPDATE "
        "USING (company_id IS NULL OR company_id = app.current_company_id()) "
        "WITH CHECK (company_id IS NULL OR company_id = app.current_company_id())"
    )
    op.execute(
        "CREATE POLICY chat_conversations_delete ON chat_conversations FOR DELETE "
        "USING (company_id IS NULL OR company_id = app.current_company_id())"
    )

    # Mensagens acompanham a visibilidade da conversa (EXISTS na conversa).
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY")
    _conversation_visible = (
        "EXISTS (SELECT 1 FROM chat_conversations c WHERE c.id = conversation_id "
        "AND (c.company_id IS NULL OR c.company_id = app.current_company_id()))"
    )
    op.execute(
        f"CREATE POLICY chat_messages_select ON chat_messages "
        f"FOR SELECT USING ({_conversation_visible})"
    )
    op.execute(
        f"CREATE POLICY chat_messages_insert ON chat_messages "
        f"FOR INSERT WITH CHECK ({_conversation_visible})"
    )
    op.execute(
        f"CREATE POLICY chat_messages_delete ON chat_messages "
        f"FOR DELETE USING ({_conversation_visible})"
    )

    # Role da limpeza TTL (criada no bootstrap init-roles.sql, secao 4.8).
    op.execute(f"GRANT SELECT, DELETE ON chat_conversations TO {_CHAT_ROLE}")
    op.execute(
        f"CREATE POLICY chat_conversations_ttl ON chat_conversations FOR SELECT "
        f"TO {_CHAT_ROLE} USING (true)"
    )
    op.execute(
        f"CREATE POLICY chat_conversations_ttl_delete ON chat_conversations FOR DELETE "
        f"TO {_CHAT_ROLE} USING (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS chat_conversations_ttl_delete ON chat_conversations")
    op.execute("DROP POLICY IF EXISTS chat_conversations_ttl ON chat_conversations")
    op.execute(f"REVOKE SELECT, DELETE ON chat_conversations FROM {_CHAT_ROLE}")
    op.drop_table("chat_messages")
    op.drop_table("chat_conversations")
