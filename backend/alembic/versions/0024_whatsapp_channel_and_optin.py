"""Canal WhatsApp para notificacoes - Fase 3, passo 4.

1) Relaxa o check de canal de ``notifications`` e ``notification_preferences``
   para aceitar WHATSAPP (padrao do ORM: ``enum_check`` com
   NotificationChannel, que agora tem EMAIL + WHATSAPP).
2) ``users`` ganha colunas NULLABLE de opt-in explicito (spec do item 3):
   ``whatsapp_phone`` (E.164), ``whatsapp_opt_in`` (default false) e
   ``whatsapp_opt_in_at``. Nulo/falso = NUNCA enviar WhatsApp. O campo
   ``users.phone`` (Fase 11) permanece intocado.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("whatsapp_phone", sa.String(20), nullable=True))
    op.add_column(
        "users",
        sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users", sa.Column("whatsapp_opt_in_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Drops via SQL direto: a naming convention do Alembic re-prefixaria
    # nomes explicitos (ck_notifications_channel -> ck_notifications_ck_...).
    op.execute("ALTER TABLE notifications DROP CONSTRAINT ck_notifications_channel")
    op.create_check_constraint("channel", "notifications", "channel IN ('EMAIL', 'WHATSAPP')")
    op.execute(
        "ALTER TABLE notification_preferences DROP CONSTRAINT ck_notification_preferences_channel"
    )
    op.create_check_constraint(
        "channel", "notification_preferences", "channel IN ('EMAIL', 'WHATSAPP')"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE notification_preferences DROP CONSTRAINT ck_notification_preferences_channel"
    )
    op.create_check_constraint("channel", "notification_preferences", "channel IN ('EMAIL')")
    op.execute("ALTER TABLE notifications DROP CONSTRAINT ck_notifications_channel")
    op.create_check_constraint("channel", "notifications", "channel IN ('EMAIL')")
    op.drop_column("users", "whatsapp_opt_in_at")
    op.drop_column("users", "whatsapp_opt_in")
    op.drop_column("users", "whatsapp_phone")
