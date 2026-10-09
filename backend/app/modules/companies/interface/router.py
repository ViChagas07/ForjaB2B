"""Endpoints do contexto de empresas (onboarding publico + consulta autenticada).

Rotas finas: traduzem HTTP <-> caso de uso. O company_id usado na consulta vem
do token autenticado (get_current_auth), nunca de um parametro do cliente.

A aprovacao de empresas usa uma chave de administrador de plataforma
(``ADMIN_API_KEY``) e nao o JWT de um tenant: um operador de plataforma nao
faz parte do tenant da empresa em aprovacao.
"""

from __future__ import annotations

import hmac
import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.companies.application.company import (
    ApproveCompany,
    CompanyView,
    GetCurrentCompany,
    RegisterCompany,
    RegisterCompanyCommand,
)
from app.modules.companies.interface.schemas import (
    CompanyResponse,
    RegisterCompanyRequest,
    RegisterCompanyResponse,
)

router = APIRouter(prefix="/companies", tags=["companies"])


def _register_usecase(request: Request) -> RegisterCompany:
    return cast(RegisterCompany, request.app.state.companies_register)


def _get_usecase(request: Request) -> GetCurrentCompany:
    return cast(GetCurrentCompany, request.app.state.companies_get)


def _approve_usecase(request: Request) -> ApproveCompany:
    return cast(ApproveCompany, request.app.state.companies_approve)


@router.post("", response_model=RegisterCompanyResponse, status_code=status.HTTP_201_CREATED)
async def register_company(
    payload: RegisterCompanyRequest,
    use_case: Annotated[RegisterCompany, Depends(_register_usecase)],
) -> RegisterCompanyResponse:
    result = await use_case.register(
        RegisterCompanyCommand(
            cnpj=payload.cnpj,
            legal_name=payload.legal_name,
            trade_name=payload.trade_name,
            admin_full_name=payload.admin_full_name,
            admin_email=payload.admin_email,
            admin_cpf=payload.admin_cpf,
            password=payload.password,
        )
    )
    return RegisterCompanyResponse(
        company=CompanyResponse(
            id=result.company_id,
            cnpj=result.cnpj,
            legal_name=result.legal_name,
            trade_name=payload.trade_name,
            status=result.status,
        ),
        admin_user_id=result.admin_user_id,
    )


@router.get("/me", response_model=CompanyResponse, status_code=status.HTTP_200_OK)
async def get_current_company(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetCurrentCompany, Depends(_get_usecase)],
) -> CompanyResponse:
    view: CompanyView = await use_case.get(auth.company_id)
    return CompanyResponse(
        id=view.id,
        cnpj=view.cnpj,
        legal_name=view.legal_name,
        trade_name=view.trade_name,
        status=view.status,
    )


@router.post("/{company_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_company(
    company_id: uuid.UUID,
    request: Request,
    use_case: Annotated[ApproveCompany, Depends(_approve_usecase)],
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> Response:
    expected = cast(str | None, request.app.state.settings.admin_api_key)
    if x_admin_key is None or expected is None or not hmac.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updated = await use_case.approve(company_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
