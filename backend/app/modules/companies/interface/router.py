"""Endpoints do contexto de empresas (onboarding publico + consulta autenticada).

Rotas finas: traduzem HTTP <-> caso de uso. O company_id usado na consulta vem
do token autenticado (get_current_auth), nunca de um parametro do cliente.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.companies.application.company import (
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
