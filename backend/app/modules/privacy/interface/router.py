"""Endpoints do contexto de privacidade (direitos do titular, LGPD).

Self-service e tenant-scoped: ``company_id``/``user_id`` vem do token
autenticado, nunca de parametro do cliente. A exclusao e anonimizacao.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.privacy.application.ports import PersonalDataView
from app.modules.privacy.application.privacy import (
    DeletePersonalData,
    ExportPersonalData,
    GetConsentState,
    RecordConsent,
    RectifyPersonalData,
)
from app.modules.privacy.interface.schemas import (
    AuditEntryResponse,
    ConsentRequest,
    ConsentResponse,
    PersonalDataResponse,
    RectifyRequest,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _export_usecase(request: Request) -> ExportPersonalData:
    return cast(ExportPersonalData, request.app.state.privacy_export)


def _rectify_usecase(request: Request) -> RectifyPersonalData:
    return cast(RectifyPersonalData, request.app.state.privacy_rectify)


def _delete_usecase(request: Request) -> DeletePersonalData:
    return cast(DeletePersonalData, request.app.state.privacy_delete)


def _record_usecase(request: Request) -> RecordConsent:
    return cast(RecordConsent, request.app.state.privacy_record_consent)


def _get_consent_usecase(request: Request) -> GetConsentState:
    return cast(GetConsentState, request.app.state.privacy_get_consent)


def _to_response(view: PersonalDataView) -> PersonalDataResponse:
    return PersonalDataResponse(
        user_id=view.user_id,
        company_id=view.company_id,
        email=view.email,
        full_name=view.full_name,
        phone=view.phone,
        status=view.status,
        role=view.role,
        email_verified_at=view.email_verified_at,
        last_login_at=view.last_login_at,
        consents=[
            ConsentResponse(
                purpose=c.purpose, action=c.action, version=c.version, consented_at=c.consented_at
            )
            for c in view.consents
        ],
        audit_entries=[
            AuditEntryResponse(
                action=a.action,
                resource=a.resource,
                resource_id=a.resource_id,
                created_at=a.created_at,
            )
            for a in view.audit_entries
        ],
    )


@router.get("/export", response_model=PersonalDataResponse, status_code=status.HTTP_200_OK)
async def export_personal_data(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[ExportPersonalData, Depends(_export_usecase)],
) -> PersonalDataResponse:
    return _to_response(await use_case.export(auth.company_id, auth.user_id))


@router.patch("/me", response_model=PersonalDataResponse, status_code=status.HTTP_200_OK)
async def rectify_personal_data(
    payload: RectifyRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[RectifyPersonalData, Depends(_rectify_usecase)],
) -> PersonalDataResponse:
    view = await use_case.rectify(
        company_id=auth.company_id,
        user_id=auth.user_id,
        full_name=payload.full_name,
        phone=payload.phone,
    )
    return _to_response(view)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_personal_data(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[DeletePersonalData, Depends(_delete_usecase)],
) -> None:
    await use_case.delete(auth.company_id, auth.user_id)


@router.post("/consent", status_code=status.HTTP_204_NO_CONTENT)
async def record_consent(
    payload: ConsentRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[RecordConsent, Depends(_record_usecase)],
) -> None:
    await use_case.record(
        company_id=auth.company_id,
        user_id=auth.user_id,
        purpose=payload.purpose,
        action=payload.action,
        version=payload.version,
        document_hash=payload.document_hash,
    )


@router.get("/consent", response_model=list[ConsentResponse], status_code=status.HTTP_200_OK)
async def get_consent_state(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetConsentState, Depends(_get_consent_usecase)],
) -> list[ConsentResponse]:
    return [
        ConsentResponse(
            purpose=c.purpose, action=c.action, version=c.version, consented_at=c.consented_at
        )
        for c in await use_case.get(auth.company_id, auth.user_id)
    ]
