"""Perfil da propria conta (nome, telefone, nascimento, genero e CEP)."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.identity.application.account import (
    AccountProfile,
    GetAccount,
    UpdateAccount,
    UpdateAccountCommand,
)
from app.modules.identity.interface.schemas import (
    AccountProfileResponse,
    UpdateAccountRequest,
)

router = APIRouter(prefix="/account", tags=["account"])


def _get_usecase(request: Request) -> GetAccount:
    return cast(GetAccount, request.app.state.account_get)


def _update_usecase(request: Request) -> UpdateAccount:
    return cast(UpdateAccount, request.app.state.account_update)


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


def _to_response(profile: AccountProfile) -> AccountProfileResponse:
    return AccountProfileResponse(
        id=profile.id,
        email=profile.email,
        full_name=profile.full_name,
        phone=profile.phone,
        birth_date=profile.birth_date,
        gender=profile.gender,
        postal_code=profile.postal_code,
        account_type=profile.account_type,
        role=profile.role,
    )
