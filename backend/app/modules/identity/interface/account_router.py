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
    UpdateAccountCurrency,
    UpdateAccountCurrencyCommand,
)
from app.modules.identity.interface.schemas import (
    AccountPreferencesRequest,
    AccountPreferencesResponse,
    AccountProfileResponse,
    DisplayCurrency,
    UpdateAccountRequest,
)

router = APIRouter(prefix="/account", tags=["account"])


def _get_usecase(request: Request) -> GetAccount:
    return cast(GetAccount, request.app.state.account_get)


def _update_usecase(request: Request) -> UpdateAccount:
    return cast(UpdateAccount, request.app.state.account_update)


def _update_currency_usecase(request: Request) -> UpdateAccountCurrency:
    return cast(UpdateAccountCurrency, request.app.state.account_update_currency)


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
        display_currency=cast(DisplayCurrency, profile.display_currency)
    )


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
        account_type=profile.account_type,
        role=profile.role,
    )
