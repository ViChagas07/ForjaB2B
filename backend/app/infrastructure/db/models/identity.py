"""Mapeadores ORM do contexto de identidade (User, CompanyMember).

Privacidade (MEGA-PROMPT, secao 5/8): o CPF nunca e armazenado em texto claro.
- ``cpf_hash``: HMAC-SHA256(cpf, pepper), unico, garante "um CPF, uma conta".
- ``cpf_encrypted``: valor criptografado (AES-GCM/Fernet) para exibicao
  mascarada. A computacao de hash/criptografia e da Fase 2 (backend+security);
  aqui ficam apenas as colunas persistidas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

from app.domain.consumer import Gender
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
    __table_args__ = (
        enum_check("status", UserStatus),
        enum_check("gender", Gender),
        CheckConstraint(
            "postal_code IS NULL OR postal_code ~ '^[0-9]{8}$'",
            name="postal_code_format",
        ),
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

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, native_enum=False, create_constraint=False, length=24)
    )
    postal_code: Mapped[str | None] = mapped_column(String(8))
    # Preferencia de EXIBICAO. A cobranca e sempre em BRL; a coluna so
    # preserva a escolha do usuario entre sessoes/dispositivos.
    display_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="BRL", server_default=text("'BRL'")
    )
    # Foto de perfil. Os bytes ficam no banco (2 MB max) e o frontend usa a
    # URL publica com a chave aleatoria; `deferred` evita carregar a imagem em
    # toda leitura de perfil.
    avatar_key: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    avatar_content_type: Mapped[str | None] = mapped_column(String(32))
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # WhatsApp (Fase 3, recuperacao de carrinho): opt-in EXPLICITO do usuario.
    # Nulo/falso = NUNCA enviar. `whatsapp_phone` e o numero E.164 confirmado.
    whatsapp_phone: Mapped[str | None] = mapped_column(String(20))
    whatsapp_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    consumer_profile: Mapped[ConsumerProfile | None] = relationship(
        back_populates="user", uselist=False
    )


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


class ConsumerProfile(TimestampMixin, Base):
    """Perfil pessoal do consumidor (conta ``PERSON``).

    A data de nascimento permite calcular a idade e validar maioridade sem
    armazenar um numero que envelhece. O CEP e apenas o dado inicial de
    localizacao; o endereco completo de entrega continua no fluxo de checkout.
    """

    __tablename__ = "consumer_profiles"
    __table_args__ = (
        CheckConstraint("postal_code ~ '^[0-9]{8}$'", name="postal_code_format"),
        enum_check("gender", Gender),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender, native_enum=False, create_constraint=False, length=24),
        nullable=False,
    )
    postal_code: Mapped[str] = mapped_column(String(8), nullable=False)

    user: Mapped[User] = relationship(back_populates="consumer_profile")
