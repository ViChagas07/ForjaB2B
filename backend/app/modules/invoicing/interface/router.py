"""Endpoints do contexto de faturamento (criacao/consulta).

Rotas finas: traduzem HTTP <-> caso de uso. O ``company_id`` vem do token
autenticado (get_current_auth); nada de company/order vindo do cliente.
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.security import AuthContext
from app.interface.deps import get_current_auth
from app.modules.invoicing.application.invoice import CreateInvoice, GetInvoice, GetInvoiceByOrder
from app.modules.invoicing.application.ports import InvoiceView
from app.modules.invoicing.interface.schemas import CreateInvoiceRequest, InvoiceResponse

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _create_usecase(request: Request) -> CreateInvoice:
    return cast(CreateInvoice, request.app.state.invoicing_create)


def _get_usecase(request: Request) -> GetInvoice:
    return cast(GetInvoice, request.app.state.invoicing_get)


def _get_by_order_usecase(request: Request) -> GetInvoiceByOrder:
    return cast(GetInvoiceByOrder, request.app.state.invoicing_get_by_order)


def _to_response(view: InvoiceView) -> InvoiceResponse:
    return InvoiceResponse(
        id=view.id,
        order_id=view.order_id,
        company_id=view.company_id,
        number=view.number,
        amount=view.amount,
        status=view.status,
        payment_terms=view.payment_terms,
        currency=view.currency,
        due_at=view.due_at,
        issued_at=view.issued_at,
        paid_at=view.paid_at,
        boleto_reference=view.boleto_reference,
        created_at=view.created_at,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: CreateInvoiceRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[CreateInvoice, Depends(_create_usecase)],
) -> InvoiceResponse:
    view = await use_case.create(
        company_id=auth.company_id,
        order_id=payload.order_id,
        terms=payload.payment_terms,
    )
    return _to_response(view)


@router.get("/order/{order_id}", response_model=InvoiceResponse, status_code=status.HTTP_200_OK)
async def get_invoice_by_order(
    order_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetInvoiceByOrder, Depends(_get_by_order_usecase)],
) -> InvoiceResponse:
    return _to_response(await use_case.get(auth.company_id, order_id))


@router.get("/{invoice_id}", response_model=InvoiceResponse, status_code=status.HTTP_200_OK)
async def get_invoice(
    invoice_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    use_case: Annotated[GetInvoice, Depends(_get_usecase)],
) -> InvoiceResponse:
    return _to_response(await use_case.get(auth.company_id, invoice_id))
