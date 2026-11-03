"""Persistencia da recuperacao de conta (Fase 1).

Duas tabelas novas, sem FK para ``users`` (a role de migrations pode nao ser
owner das tabelas pre-existentes em producao). A integridade e garantida pelo
codigo, que grava/le sempre no tenant resolvido; telefones sao unicos
globalmente e por usuario.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class UserVerifiedPhone(Base):
    """Telefone E.164 verificado por usuario (1:1), tenant-scoped."""

    __tablename__ = "user_verified_phones"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_verified_phones_user_id"),
        UniqueConstraint("phone_e164", name="uq_user_verified_phones_phone_e164"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UserCredentialState(Base):
    """Estado 1:1 de credencial do usuario (epoch e ultima troca de senha)."""

    __tablename__ = "user_credential_state"
    __table_args__ = (
        CheckConstraint("credential_epoch >= 0", name="credential_epoch_non_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    credential_epoch: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
