"""Mapeadores ORM do contexto de privacidade (ConsentRecord).

Trilha historica de consentimento (append-only): cada aceite/revogacao e uma
nova linha. O estado vigente e resolvido como "ultimo registro por
(usuario, finalidade)" na Fase 2; nunca se sobrescreve o registro anterior.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import enum_check
from app.modules.privacy.domain.enums import ConsentAction, ConsentPurpose

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.companies import Company
    from app.infrastructure.db.models.identity import User


class ConsentRecord(Base):
    """Registro imutavel de consentimento (LGPD)."""

    __tablename__ = "consent_records"
    __table_args__ = (
        enum_check("purpose", ConsentPurpose),
        enum_check("action", ConsentAction),
        Index("ix_consent_records_user_purpose", "user_id", "purpose"),
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
    purpose: Mapped[ConsentPurpose] = mapped_column(
        Enum(ConsentPurpose, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    action: Mapped[ConsentAction] = mapped_column(
        Enum(ConsentAction, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped[Company] = relationship(back_populates="consent_records")
    user: Mapped[User] = relationship(back_populates="consent_records")
