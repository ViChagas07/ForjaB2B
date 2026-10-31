"""Preferencias do usuario (Fase 2).

Tabela propria para armazenar preferencias que antes ficavam em colunas da
tabela `users` e que nao podem ser adicionadas la por falta de ownership em
producao. Esta tabela e nova, entao o role `forja` tem permissao total.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.identity import User


class UserPreferences(TimestampMixin, Base):
    """Preferencias do usuario (moeda, privacidade, avatar, whatsapp)."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(
            "display_currency IN ('BRL', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CNY')",
            name="display_currency",
        ),
        CheckConstraint(
            "avatar_content_type IS NULL OR "
            "avatar_content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="avatar_content_type",
        ),
        CheckConstraint(
            "(avatar_key IS NULL AND avatar_content_type IS NULL AND avatar_data IS NULL "
            "AND avatar_updated_at IS NULL) OR (avatar_key IS NOT NULL AND "
            "avatar_content_type IS NOT NULL AND avatar_data IS NOT NULL AND "
            "avatar_updated_at IS NOT NULL)",
            name="avatar_consistency",
        ),
        CheckConstraint(
            "avatar_data IS NULL OR octet_length(avatar_data) <= 2097152",
            name="avatar_size",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    display_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="BRL", server_default=text("'BRL'")
    )
    hide_spending: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    avatar_key: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    avatar_content_type: Mapped[str | None] = mapped_column(String(32))
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_phone: Mapped[str | None] = mapped_column(String(20))
    whatsapp_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="preferences")
