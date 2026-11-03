"""Perfil da propria conta (nome, telefone, nascimento, genero e CEP)."""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response

from app.application.security import AuthContext
from app.core.config import Settings
from app.core.request_context import client_ip
from app.interface.deps import get_current_auth
from app.modules.identity.application.account import (
    AccountProfile,
    GetAccount,
    UpdateAccount,
    UpdateAccountCommand,
    UpdateAccountCurrency,
    UpdateAccountCurrencyCommand,
    UpdateAccountSpendingVisibility,
    UpdateAccountSpendingVisibilityCommand,
)
from app.modules.identity.application.avatar import (
    MAX_AVATAR_BYTES,
    AvatarView,
    GetAccountAvatar,
    RemoveAccountAvatar,
    UpdateAccountAvatar,
)
from app.modules.identity.application.errors import AvatarTooLargeError
from app.modules.identity.application.phone_verification import (
    CheckPhoneVerification,
    GetPhoneVerificationStatus,
    StartPhoneVerification,
)
from app.modules.identity.interface.schemas import (
    AccountAvatarResponse,
    AccountPreferencesRequest,
    AccountPreferencesResponse,
    AccountProfileResponse,
    AccountSpendingVisibilityRequest,
    DisplayCurrency,
    PhoneVerificationAcceptedResponse,
    PhoneVerificationCheckRequest,
    PhoneVerificationCheckResponse,
    PhoneVerificationStartRequest,
    PhoneVerificationStatusResponse,
    UpdateAccountRequest,
)

router = APIRouter(prefix="/account", tags=["account"])


def _get_usecase(request: Request) -> GetAccount:
    return cast(GetAccount, request.app.state.account_get)


def _update_usecase(request: Request) -> UpdateAccount:
    return cast(UpdateAccount, request.app.state.account_update)


def _update_currency_usecase(request: Request) -> UpdateAccountCurrency:
    return cast(UpdateAccountCurrency, request.app.state.account_update_currency)


def _update_spending_visibility_usecase(request: Request) -> UpdateAccountSpendingVisibility:
    return cast(
        UpdateAccountSpendingVisibility,
        request.app.state.account_update_spending_visibility,
    )


def _upload_avatar_usecase(request: Request) -> UpdateAccountAvatar:
    return cast(UpdateAccountAvatar, request.app.state.account_upload_avatar)


def _remove_avatar_usecase(request: Request) -> RemoveAccountAvatar:
    return cast(RemoveAccountAvatar, request.app.state.account_remove_avatar)


def _get_avatar_usecase(request: Request) -> GetAccountAvatar:
    return cast(GetAccountAvatar, request.app.state.account_get_avatar)


def _phone_start_usecase(request: Request) -> StartPhoneVerification:
    return cast(StartPhoneVerification, request.app.state.account_phone_verification_start)


def _phone_check_usecase(request: Request) -> CheckPhoneVerification:
    return cast(CheckPhoneVerification, request.app.state.account_phone_verification_check)


def _phone_status_usecase(request: Request) -> GetPhoneVerificationStatus:
    return cast(GetPhoneVerificationStatus, request.app.state.account_phone_verification_status)


@router.get(
    "",
    response_model=AccountProfileResponse,
    summary="Perfil da conta autenticada",
)
async def get_account(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetAccount, Depends(_get_usecase)],
) -> AccountProfileResponse:
    return _to_response(await use_case.execute(auth))


@router.patch(
    "",
    response_model=AccountProfileResponse,
    summary="Atualizar perfil da conta",
)
async def update_account(
    payload: UpdateAccountRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[UpdateAccount, Depends(_update_usecase)],
) -> AccountProfileResponse:
    profile = await use_case.execute(
        auth,
        UpdateAccountCommand(
            full_name=payload.full_name,
            phone=payload.phone,
            birth_date=payload.birth_date,
            gender=payload.gender,
            postal_code=payload.postal_code,
        ),
    )
    return _to_response(profile)


@router.post(
    "/phone/verification/start",
    response_model=PhoneVerificationAcceptedResponse,
    status_code=202,
    summary="Enviar codigo SMS para verificar o telefone",
)
async def start_phone_verification(
    payload: PhoneVerificationStartRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[StartPhoneVerification, Depends(_phone_start_usecase)],
) -> PhoneVerificationAcceptedResponse:
    settings = cast(Settings, request.app.state.settings)
    await use_case.execute(
        auth,
        phone_e164=payload.phone,
        locale=payload.locale,
        remote_ip=client_ip(request.scope, settings.trusted_proxy_count),
    )
    return PhoneVerificationAcceptedResponse()


@router.post(
    "/phone/verification/check",
    response_model=PhoneVerificationCheckResponse,
    summary="Confirmar o codigo SMS do telefone",
)
async def check_phone_verification(
    payload: PhoneVerificationCheckRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[CheckPhoneVerification, Depends(_phone_check_usecase)],
) -> PhoneVerificationCheckResponse:
    settings = cast(Settings, request.app.state.settings)
    await use_case.execute(
        auth,
        phone_e164=payload.phone,
        code=payload.code,
        remote_ip=client_ip(request.scope, settings.trusted_proxy_count),
    )
    return PhoneVerificationCheckResponse()


@router.get(
    "/phone/verification",
    response_model=PhoneVerificationStatusResponse,
    summary="Status do telefone verificado",
)
async def get_phone_verification_status(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetPhoneVerificationStatus, Depends(_phone_status_usecase)],
) -> PhoneVerificationStatusResponse:
    status = await use_case.execute(auth)
    return PhoneVerificationStatusResponse(
        verified=status.verified, phone_masked=status.phone_masked
    )


@router.patch(
    "/preferences",
    response_model=AccountPreferencesResponse,
    summary="Atualizar preferencias do perfil",
)
async def update_preferences(
    payload: AccountPreferencesRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[UpdateAccountCurrency, Depends(_update_currency_usecase)],
) -> AccountPreferencesResponse:
    profile = await use_case.execute(
        auth,
        UpdateAccountCurrencyCommand(display_currency=payload.display_currency),
    )
    return AccountPreferencesResponse(
        display_currency=cast(DisplayCurrency, profile.display_currency),
        hide_spending=profile.hide_spending,
    )


@router.patch(
    "/preferences/spending-visibility",
    response_model=AccountPreferencesResponse,
    summary="Ocultar ou exibir os gastos no painel",
)
async def update_spending_visibility(
    payload: AccountSpendingVisibilityRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[
        UpdateAccountSpendingVisibility,
        Depends(_update_spending_visibility_usecase),
    ],
) -> AccountPreferencesResponse:
    profile = await use_case.execute(
        auth,
        UpdateAccountSpendingVisibilityCommand(hide_spending=payload.hide_spending),
    )
    return AccountPreferencesResponse(
        display_currency=cast(DisplayCurrency, profile.display_currency),
        hide_spending=profile.hide_spending,
    )


@router.put(
    "/avatar",
    response_model=AccountAvatarResponse,
    summary="Enviar foto de perfil",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/webp": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def upload_avatar(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[UpdateAccountAvatar, Depends(_upload_avatar_usecase)],
) -> AccountAvatarResponse:
    data = await _read_avatar_body(request)
    return _to_avatar_response(await use_case.execute(auth, data))


@router.delete(
    "/avatar",
    response_model=AccountAvatarResponse,
    summary="Remover foto de perfil",
)
async def remove_avatar(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[RemoveAccountAvatar, Depends(_remove_avatar_usecase)],
) -> AccountAvatarResponse:
    return _to_avatar_response(await use_case.execute(auth))


@router.get(
    "/avatar/{company_id}/{user_id}/{avatar_key}",
    response_class=Response,
    summary="Avatar publico por chave aleatoria",
)
async def get_account_avatar(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    avatar_key: uuid.UUID,
    use_case: Annotated[GetAccountAvatar, Depends(_get_avatar_usecase)],
) -> Response:
    avatar = await use_case.execute(company_id=company_id, user_id=user_id, avatar_key=avatar_key)
    return Response(
        content=avatar.data,
        media_type=avatar.content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{avatar_key}"',
        },
    )


async def _read_avatar_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_AVATAR_BYTES:
                raise AvatarTooLargeError()
        except ValueError:
            pass

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_AVATAR_BYTES:
            raise AvatarTooLargeError()
        chunks.append(chunk)
    return b"".join(chunks)


def _to_avatar_response(view: AvatarView) -> AccountAvatarResponse:
    return AccountAvatarResponse(avatar_url=view.avatar_url, updated_at=view.updated_at)


def _to_response(profile: AccountProfile) -> AccountProfileResponse:
    return AccountProfileResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        phone=profile.phone,
        birth_date=profile.birth_date,
        gender=profile.gender,
        postal_code=profile.postal_code,
        display_currency=cast(DisplayCurrency, profile.display_currency),
        avatar_url=profile.avatar_url,
        account_type=profile.account_type,
        role=profile.role,
        hide_spending=profile.hide_spending,
    )
