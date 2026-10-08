"""Portas (interfaces) da camada de aplicacao.

Implementacoes concretas vivem na camada de infraestrutura e sao ligadas na
raiz de composicao (app.main).
"""

from app.application.ports.repository import Repository
from app.application.ports.tenant import TenantContext, TenantContextProvider
from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "Repository",
    "TenantContext",
    "TenantContextProvider",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
