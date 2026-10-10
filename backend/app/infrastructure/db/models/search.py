"""Mapeador ORM da outbox de sincronizacao do indice de busca (SearchOutbox).

A tabela e GLOBAL (como o catalogo): sem RLS e sem ``company_id``. O evento e
gravado na SAME transacao de uma futura alteracao de produto (padrao outbox) e
processado depois pelo worker; falhas ficam registradas (status/attempts/
last_error) e sao reprocessaveis.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.common import TimestampMixin


class SearchOutbox(TimestampMixin, Base):
    """Linha da outbox de sincronizacao do indice de busca (global)."""

    __tablename__ = "search_outbox"
    __table_args__ = (
        CheckConstraint("event_type IN ('UPSERT', 'DELETE')", name="event_type"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'FAILED', 'DEAD_LETTERED')",
            name="status",
        ),
        Index("ix_search_outbox_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'product'")
    )
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(BigInteger(), nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'PENDING'")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
