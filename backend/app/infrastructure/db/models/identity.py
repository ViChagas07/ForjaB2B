"""Mapeadores ORM do contexto de identidade (User, CompanyMember).

Privacidade (MEGA-PROMPT, secao 5/8): o CPF nunca e armazenado em texto claro.
- ``cpf_hash``: HMAC-SHA256(cpf, pepper), unico, garante "um CPF, uma conta".
- ``cpf_encrypted``: valor criptografado (AES-GCM/Fernet) para exibicao
  mascarada. A computacao de hash/criptografia e da Fase 2 (backend+security);
  aqui ficam apenas as colunas persistidas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin, enum_check
from app.modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.audit import AuditLog
    from app.infrastructure.db.models.companies import Company
    from app.infrastructure.db.models.external_identity import UserExternalIdentity
    from app.infrastructure.db.models.ordering import Order
    from app.infrastructure.db.models.privacy import ConsentRecord


class User(TimestampMixin, Base):
    """Usuario (conta) vinculado a uma empresa. Email e cpf_hash sao unicos."""

    __tablename__ = "users"
    __table_args__ = (enum_check("status", UserStatus),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    cpf_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    cpf_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=UserStatus.PENDING_EMAIL.value,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="users")
    members: Mapped[list[CompanyMember]] = relationship(back_populates="user")
    orders: Mapped[list[Order]] = relationship(back_populates="buyer")
    consent_records: Mapped[list[ConsentRecord]] = relationship(back_populates="user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
    external_identities: Mapped[list[UserExternalIdentity]] = relationship(back_populates="user")


class CompanyMember(TimestampMixin, Base):
    """Vinculo usuario x empresa com papel (team management)."""

    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_members_company_user"),
        enum_check("role", MemberRole),
        enum_check("status", MemberStatus),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=MemberRole.BUYER.value,
    )
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=MemberStatus.ACTIVE.value,
    )

    company: Mapped[Company] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="members")
