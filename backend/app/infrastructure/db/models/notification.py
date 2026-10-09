"""Mapeadores ORM do contexto de notificacao (Notification, NotificationPreference).

``notifications`` e a outbox transacional: eventos de negocio viram linhas
PENDING na mesma transacao e o worker despacha (envia e-mail) depois. O conteudo
(payload) e gravado no write; o e-mail e montado no despacho, com idioma do
destinatario. ``notification_preferences`` registra opt-out por canal.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin, enum_check
from app.modules.notification.domain.enums import NotificationChannel, NotificationStatus


class Notification(TimestampMixin, Base):
    """Linha da outbox de notificacoes (tenant-scoped)."""

    __tablename__ = "notifications"
    __table_args__ = (
        enum_check("status", NotificationStatus),
        enum_check("channel", NotificationChannel),
        Index("ix_notifications_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=NotificationChannel.EMAIL.value,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=NotificationStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(TimestampMixin, Base):
    """Preferencia de comunicacao por usuario/canal (opt-out)."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        enum_check("channel", NotificationChannel),
        Index("uq_notification_preferences_scope", "company_id", "user_id", "channel", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
