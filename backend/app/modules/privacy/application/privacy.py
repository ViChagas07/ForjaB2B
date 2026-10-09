"""Casos de uso do contexto de privacidade (direitos do titular, LGPD).

Todos os casos de uso operam sobre o TITULAR autenticado (self-service) e sao
tenant-scoped (RLS): o company_id vem do token e nunca de parametro do cliente.
A exclusao e anonimizacao (preserva registros financeiros/fiscais/auditoria).
"""

from __future__ import annotations

import uuid

from app.modules.privacy.application.errors import PersonalDataNotFoundError
from app.modules.privacy.application.ports import (
    ConsentView,
    PersonalDataView,
    PrivacyRepository,
)
from app.modules.privacy.domain.enums import ConsentAction, ConsentPurpose


class ExportPersonalData:
    """Caso de uso: exporta os dados pessoais do titular."""

    def __init__(self, *, repository: PrivacyRepository) -> None:
        self._repository = repository

    async def export(self, company_id: uuid.UUID, user_id: uuid.UUID) -> PersonalDataView:
        data = await self._repository.get_personal_data(company_id, user_id)
        if data is None:
            raise PersonalDataNotFoundError()
        return data


class RectifyPersonalData:
    """Caso de uso: retifica nome/telefone do titular."""

    def __init__(self, *, repository: PrivacyRepository) -> None:
        self._repository = repository

    async def rectify(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        full_name: str,
        phone: str | None,
    ) -> PersonalDataView:
        await self._repository.rectify(
            company_id=company_id, user_id=user_id, full_name=full_name, phone=phone
        )
        data = await self._repository.get_personal_data(company_id, user_id)
        if data is None:
            raise PersonalDataNotFoundError()
        return data


class DeletePersonalData:
    """Caso de uso: anonimiza os dados pessoais do titular."""

    def __init__(self, *, repository: PrivacyRepository) -> None:
        self._repository = repository

    async def delete(self, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self._repository.anonymize(company_id=company_id, user_id=user_id)


class RecordConsent:
    """Caso de uso: registra aceite/revogacao de consentimento (versionado)."""

    def __init__(self, *, repository: PrivacyRepository) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        purpose: ConsentPurpose,
        action: ConsentAction,
        version: str,
        document_hash: str,
    ) -> None:
        await self._repository.record_consent(
            company_id=company_id,
            user_id=user_id,
            purpose=purpose,
            action=action,
            version=version,
            document_hash=document_hash,
        )


class GetConsentState:
    """Caso de uso: consulta o estado vigente de consentimento do titular."""

    def __init__(self, *, repository: PrivacyRepository) -> None:
        self._repository = repository

    async def get(self, company_id: uuid.UUID, user_id: uuid.UUID) -> list[ConsentView]:
        return await self._repository.get_current_consents(company_id, user_id)
