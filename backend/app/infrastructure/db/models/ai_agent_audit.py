"""Mapeador ORM do log de auditoria de agentes de IA (AgentAuditLog).

Tabela append-only (sem update/delete no ciclo de vida): registra eventos
dos agentes de IA (recuperacao de carrinho, chat) para observabilidade e
investigacao. TENANT-SCOPED quando `company_id` e informado (FORCE ROW LEVEL
SECURITY); linhas com `company_id` NULL (chat de visitante) ficam invisiveis
para qualquer tenant.

Privacidade por construcao (ver `app.modules.ai.domain.audit_payload`):
`payload` guarda APENAS hash sha256 do texto, tamanho em caracteres e os
primeiros 80 caracteres sanitizados — nunca o texto completo do usuario,
PII (CNPJ, e-mail, telefone), precos ou segredos. Este mapeador existe
tambem para o `Base.metadata` (drift detection do Alembic).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base

AGENT_KINDS = ("cart", "chat")
GUARD_VERDICTS = ("ALLOW", "BLOCK")


class AgentAuditLog(Base):
    """Evento append-only de auditoria de agente de IA."""

    __tablename__ = "agent_audit_log"
    __table_args__ = (
        CheckConstraint("agent IN ('cart', 'chat')", name="agent"),
        CheckConstraint("verdict IS NULL OR verdict IN ('ALLOW', 'BLOCK')", name="verdict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent: Mapped[str] = mapped_column(String(16), nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    verdict: Mapped[str | None] = mapped_column(String(24))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()"), index=True
    )
