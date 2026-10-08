"""Router agregador da API v1.

Cada bounded context contribui com seu proprio router. A ordem de inclusao nao
muda semantica; o prefixo /api/v1 e unico para toda a API.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.cart.interface.router import router as cart_router
from app.modules.catalog.interface.router import router as catalog_router
from app.modules.companies.interface.router import router as companies_router
from app.modules.credit.interface.router import router as credit_router
from app.modules.identity.interface.router import router as identity_router
from app.modules.invoicing.interface.router import router as invoicing_router
from app.modules.ordering.interface.router import router as ordering_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(identity_router)
api_v1_router.include_router(companies_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(credit_router)
api_v1_router.include_router(cart_router)
api_v1_router.include_router(ordering_router)
api_v1_router.include_router(invoicing_router)
