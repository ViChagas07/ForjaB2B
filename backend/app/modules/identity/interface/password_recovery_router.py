"""Rotas da recuperacao de conta por e-mail (request, verify e reset)."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import Settings
from app.core.request_context import client_ip
from app.modules.identity.application.password_recovery import (
    PasswordRecoveryCommand,
    RequestPasswordRecovery,
    ResetPassword,
    VerifyPasswordRecoveryCode,
)
from app.modules.identity.interface.schemas import (
    PasswordRecoveryAcceptedResponse,
    PasswordRecoveryRequest,
    PasswordRecoveryResetRequest,
    PasswordRecoveryVerifiedResponse,
    PasswordRecoveryVerifyRequest,
)

router = APIRouter(prefix="/auth/password-recovery", tags=["auth"])


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _ensure_enabled(settings: Settings) -> None:
    if not settings.password_recovery_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def _request_usecase(request: Request) -> RequestPasswordRecovery:
    return cast(RequestPasswordRecovery, request.app.state.password_recovery_request)


def _verify_usecase(request: Request) -> VerifyPasswordRecoveryCode:
    return cast(VerifyPasswordRecoveryCode, request.app.state.password_recovery_verify)


def _reset_usecase(request: Request) -> ResetPassword:
    return cast(ResetPassword, request.app.state.password_recovery_reset)


@router.post(
    "/request",
    response_model=PasswordRecoveryAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar codigo de recuperacao de conta",
)
async def request_password_recovery(
    payload: PasswordRecoveryRequest,
    request: Request,
) -> PasswordRecoveryAcceptedResponse:
    settings = _settings(request)
    _ensure_enabled(settings)
    await _request_usecase(request).execute(
        PasswordRecoveryCommand(
            email=payload.email,
            phone_e164=payload.phone,
            turnstile_token=payload.turnstile_token,
            locale=payload.locale,
            remote_ip=client_ip(request.scope, settings.trusted_proxy_count),
        )
    )
    return PasswordRecoveryAcceptedResponse()


@router.post(
    "/verify",
    response_model=PasswordRecoveryVerifiedResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar codigo e obter reset_token",
)
async def verify_password_recovery_code(
    payload: PasswordRecoveryVerifyRequest,
    request: Request,
) -> PasswordRecoveryVerifiedResponse:
    settings = _settings(request)
    _ensure_enabled(settings)
    result = await _verify_usecase(request).execute(
        email=payload.email,
        phone_e164=payload.phone,
        code=payload.code,
        remote_ip=client_ip(request.scope, settings.trusted_proxy_count),
    )
    return PasswordRecoveryVerifiedResponse(
        reset_token=result.reset_token, expires_in=result.expires_in
    )


@router.post(
    "/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Definir nova senha com reset_token",
)
async def reset_password(
    payload: PasswordRecoveryResetRequest,
    request: Request,
) -> None:
    settings = _settings(request)
    _ensure_enabled(settings)
    await _reset_usecase(request).execute(
        reset_token=payload.reset_token,
        new_password=payload.new_password,
        remote_ip=client_ip(request.scope, settings.trusted_proxy_count),
    )
