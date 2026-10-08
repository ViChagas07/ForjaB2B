"""Endpoints de leitura do credito (conta + ledger), tenant-scoped.

As operacoes de escrita (reserva/liberacao) sao internas e executadas pelo
contexto de Ordering dentro da propria transacao do pedido; nao sao expostas
como endpoints publicos (operacoes financeiras sensiveis).
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.credit.application.credit import GetCreditAccount, ListCreditEntries
from app.modules.credit.interface.schemas import CreditAccountResponse, CreditEntryResponse

router = APIRouter(prefix="/credit", tags=["credit"])


def _get_account(request: Request) -> GetCreditAccount:
    return cast(GetCreditAccount, request.app.state.credit_get_account)


def _list_entries(request: Request) -> ListCreditEntries:
    return cast(ListCreditEntries, request.app.state.credit_list_entries)


@router.get("/account", response_model=CreditAccountResponse, status_code=status.HTTP_200_OK)
async def get_account(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetCreditAccount, Depends(_get_account)],
) -> CreditAccountResponse:
    view = await use_case.get(auth.company_id)
    return CreditAccountResponse(
        company_id=view.company_id,
        credit_limit=view.credit_limit,
        used=view.used,
        available=view.available,
        currency=view.currency,
    )


@router.get("/entries", response_model=list[CreditEntryResponse], status_code=status.HTTP_200_OK)
async def list_entries(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[ListCreditEntries, Depends(_list_entries)],
) -> list[CreditEntryResponse]:
    views = await use_case.list(auth.company_id)
    return [
        CreditEntryResponse(
            id=v.id,
            entry_type=v.entry_type,
            amount=v.amount,
            reference_type=v.reference_type,
            reference_id=v.reference_id,
            description=v.description,
            created_at=v.created_at,
        )
        for v in views
    ]
