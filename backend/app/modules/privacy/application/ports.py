"""Portas do contexto de privacidade (contratos de dependencias invertidas)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.privacy.domain.enums import ConsentAction, ConsentPurpose


@dataclass(frozen=True, kw_only=True)
class ConsentView:
    """Registro de consentimento (ultimo por finalidade)."""

    purpose: str
    action: str
    version: str
    consented_at: datetime


@dataclass(frozen=True, kw_only=True)
class AuditEntryView:
    """Entrada de auditoria sobre o titular."""

    action: str
    resource: str
    resource_id: uuid.UUID
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class PersonalDataView:
    """Dados pessoais do titular + trilhas (consentimento/auditoria)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    status: str
    role: str | None
    email_verified_at: datetime | None
    last_login_at: datetime | None
    consents: list[ConsentView]
    audit_entries: list[AuditEntryView]


class PrivacyRepository(Protocol):
    """Persistencia de dados pessoais + consentimento + auditoria (tenant-scoped)."""

    async def get_personal_data(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> PersonalDataView | None:
        """Devolve os dados pessoais do titular (com consents/auditoria)."""

    async def rectify(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        full_name: str,
        phone: str | None,
    ) -> None:
        """Atualiza nome/telefone e registra auditoria na mesma transacao."""

    async def anonymize(self, *, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Anonimiza dados pessoais (preserva financeiro/fiscal/auditoria)."""

    async def record_consent(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        purpose: ConsentPurpose,
        action: ConsentAction,
        version: str,
        document_hash: str,
    ) -> None:
        """Registra um aceite/revogacao (append-only, versionado)."""

    async def get_current_consents(
        self, company_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ConsentView]:
        """Estado vigente de consentimento (ultimo por finalidade)."""
