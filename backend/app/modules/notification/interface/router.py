"""Endpoints administrativos do contexto de notificacao.

Listagem e reenvio sao restritos a papeis administrativos (ADMIN/FINANCE). A
outbox e despachada pelo worker (Celery); a API so consulta e reabre reenvios.
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext, require_any_role
from app.interface.deps import get_current_auth
from app.modules.notification.application.notification import (
    ListNotifications,
    ResendNotification,
    UpdateWhatsAppOptIn,
)
from app.modules.notification.application.ports import OutboxView
from app.modules.notification.interface.schemas import (
    NotificationResponse,
    WhatsAppOptInRequest,
    WhatsAppOptInResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

_ADMIN_ROLES = {"ADMIN", "FINANCE"}


def _list_usecase(request: Request) -> ListNotifications:
    return cast(ListNotifications, request.app.state.notification_list)


def _resend_usecase(request: Request) -> ResendNotification:
    return cast(ResendNotification, request.app.state.notification_resend)


def _whatsapp_usecase(request: Request) -> UpdateWhatsAppOptIn:
    return cast(UpdateWhatsAppOptIn, request.app.state.notification_whatsapp)


def _to_response(view: OutboxView) -> NotificationResponse:
    return NotificationResponse(
        id=view.id,
        company_id=view.company_id,
        event_type=view.event_type,
        aggregate_id=view.aggregate_id,
        status=view.status,
        attempts=view.attempts,
        error=None,
        created_at=view.created_at,
    )


@router.get("", response_model=list[NotificationResponse], status_code=status.HTTP_200_OK)
async def list_notifications(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[ListNotifications, Depends(_list_usecase)],
) -> list[NotificationResponse]:
    require_any_role(auth, _ADMIN_ROLES)
    return [_to_response(v) for v in await use_case.list(auth.company_id)]


@router.post("/{notification_id}/resend", status_code=status.HTTP_204_NO_CONTENT)
async def resend_notification(
    notification_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[ResendNotification, Depends(_resend_usecase)],
) -> None:
    require_any_role(auth, _ADMIN_ROLES)
    await use_case.resend(auth.company_id, notification_id)


@router.put("/whatsapp/preferences", response_model=WhatsAppOptInResponse)
async def update_whatsapp_preferences(
    body: WhatsAppOptInRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[UpdateWhatsAppOptIn, Depends(_whatsapp_usecase)],
) -> WhatsAppOptInResponse:
    """Ativa/desativa o canal WhatsApp do USUARIO AUTENTICADO (opt-in explicito).

    user_id/company_id vem do JWT (nunca do corpo). Falha de validacao E.164
    responde 422 com mensagem neutra.
    """
    await use_case.update(
        company_id=auth.company_id,
        user_id=auth.user_id,
        phone=body.whatsapp_phone,
        opt_in=body.opt_in,
    )
    return WhatsAppOptInResponse(
        opt_in=body.opt_in,
        whatsapp_phone=body.whatsapp_phone if body.opt_in else None,
    )
