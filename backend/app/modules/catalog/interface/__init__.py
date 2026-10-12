"""Camada interface do modulo catalog."""

from app.modules.catalog.interface.admin_router import router as admin_router
from app.modules.catalog.interface.router import router as public_router

__all__ = ["admin_router", "public_router"]
