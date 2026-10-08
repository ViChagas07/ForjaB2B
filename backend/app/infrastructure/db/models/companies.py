"""Mapeadores ORM do contexto de empresas (Company, CompanyAddress).

A tabela ``companies`` e a raiz de tenant: ``companies.id`` e o proprio
``company_id`` usado nas policies RLS das demais tabelas. Nao existe uma
coluna ``company_id`` em ``companies`` (seria redundante consigo mesma).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin, enum_check
from app.modules.companies.domain.enums import AddressType, CompanyStatus

if TYPE_CHECKING:  # pragma: no cover - apenas para o type checker
    from app.infrastructure.db.models.audit import AuditLog
    from app.infrastructure.db.models.credit import CreditAccount, CreditEntry
    from app.infrastructure.db.models.identity import CompanyMember, User
    from app.infrastructure.db.models.invoicing import Invoice
    from app.infrastructure.db.models.ordering import Order
    from app.infrastructure.db.models.privacy import ConsentRecord


class Company(TimestampMixin, Base):
    """Empresa B2B (tenant). CNPJ normalizado em 14 digitos, unico."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("cnpj ~ '^[0-9]{14}$'", name="cnpj_format"),
        enum_check("status", CompanyStatus),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, unique=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200))
    state_registration: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(CompanyStatus, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=CompanyStatus.PENDING.value,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    addresses: Mapped[list[CompanyAddress]] = relationship(back_populates="company")
    members: Mapped[list[CompanyMember]] = relationship(back_populates="company")
    users: Mapped[list[User]] = relationship(back_populates="company")
    orders: Mapped[list[Order]] = relationship(back_populates="company")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="company")
    consent_records: Mapped[list[ConsentRecord]] = relationship(back_populates="company")
    credit_account: Mapped[CreditAccount | None] = relationship(
        back_populates="company", uselist=False
    )
    credit_entries: Mapped[list[CreditEntry]] = relationship(back_populates="company")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="company")


class CompanyAddress(TimestampMixin, Base):
    """Endereco de entrega/cobranca de uma empresa."""

    __tablename__ = "company_addresses"
    __table_args__ = (enum_check("address_type", AddressType),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    address_type: Mapped[AddressType] = mapped_column(
        Enum(AddressType, native_enum=False, create_constraint=False, length=24),
        nullable=False,
        server_default=AddressType.SHIPPING.value,
    )
    street: Mapped[str] = mapped_column(String(200), nullable=False)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    complement: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(8), nullable=False)
    is_default: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))

    company: Mapped[Company] = relationship(back_populates="addresses")
