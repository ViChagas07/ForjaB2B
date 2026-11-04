"""Idioma da conversa/mensagem do chat (Fase 1 do idioma dinamico).

Adiciona duas colunas nullable:
- ``chat_conversations.conversation_language``: idioma corrente da conversa;
- ``chat_messages.language``: idioma detectado em cada mensagem.

As tabelas sao pre-existentes (0026). Para nao depender de ownership da role de
migrations no Render, o upgrade usa os helpers de ``app.core.migration_helpers``
(raw SQL com cheque de ownership) em vez de ``op.add_column``. O backfill e
idempotente e so roda quando as colunas existem. Nenhum ownership e alterado.

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op
from app.core.migration_helpers import add_column_if_owner, is_owner

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOCALES = "'pt-BR','en','zh-CN','ja','ko','ru','es','de','fr','it','ar'"
_BACKFILL = """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_conversations'
      AND column_name = 'conversation_language'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'chat_messages'
      AND column_name = 'language'
  ) THEN
    UPDATE public.chat_conversations
    SET conversation_language = locale
    WHERE conversation_language IS NULL;

    UPDATE public.chat_messages AS m
    SET language = COALESCE(c.conversation_language, c.locale)
    FROM public.chat_conversations AS c
    WHERE m.conversation_id = c.id AND m.language IS NULL;
  END IF;
END $$;
"""


def _add_language_constraint(table: str, column: str, name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = '{table}'
              AND column_name = '{column}'
          ) AND NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = '{name}'
          ) THEN
            ALTER TABLE public.{table}
            ADD CONSTRAINT {name}
            CHECK ({column} IS NULL OR {column} IN ({_LOCALES}));
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    conn = op.get_bind()
    add_column_if_owner(conn, "chat_conversations", "conversation_language", "VARCHAR(16)")
    add_column_if_owner(conn, "chat_messages", "language", "VARCHAR(16)")
    op.execute(_BACKFILL)
    if is_owner(conn, "chat_conversations"):
        _add_language_constraint(
            "chat_conversations",
            "conversation_language",
            "chat_conversations_conversation_language_check",
        )
    if is_owner(conn, "chat_messages"):
        _add_language_constraint("chat_messages", "language", "chat_messages_language_check")


def downgrade() -> None:
    conn = op.get_bind()
    if is_owner(conn, "chat_messages"):
        op.execute(
            "ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_language_check"
        )
        op.execute("ALTER TABLE chat_messages DROP COLUMN IF EXISTS language")
    if is_owner(conn, "chat_conversations"):
        op.execute(
            "ALTER TABLE chat_conversations "
            "DROP CONSTRAINT IF EXISTS chat_conversations_conversation_language_check"
        )
        op.execute("ALTER TABLE chat_conversations DROP COLUMN IF EXISTS conversation_language")
