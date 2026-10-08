"""Mapeador ORM da identidade externa (login social).

Vincula um usuario a uma identidade externa (provider + subject). O email
continua sendo a chave de resolucao; o subject e a chave de vinculo (impede
que a mesma identidade seja ligada a dois usuarios). Tenant-scoped com RLS.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.identity import User


class UserExternalIdentity(TimestampMixin, Base):
    """Vinculo usuario x identidade externa (provider + subject)."""

    __tablename__ = "user_external_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider", "subject", name="uq_user_external_identities_provider_subject"
        ),
        Index("ix_user_external_identities_user_id", "user_id"),
        Index("ix_user_external_identities_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)

    user: Mapped[User] = relationship(back_populates="external_identities")
