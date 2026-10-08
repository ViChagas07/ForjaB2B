"""Vocabulario de estado do modulo companies (pure Python, sem frameworks).

Os valores sao a fonte de verdade para as colunas de status no banco e para
as constraints CHECK das migrations. Nenhuma regra de negocio vive aqui na
Fase 1: apenas o conjunto fechado de estados aceitos pela persistencia.
"""

from __future__ import annotations

from enum import StrEnum


class CompanyStatus(StrEnum):
    """Ciclo de vida de uma empresa no onboarding B2B."""

    PENDING = "PENDING"  # aguardando aprovacao manual do backoffice
    ACTIVE = "ACTIVE"  # aprovada e operacional
    SUSPENDED = "SUSPENDED"  # bloqueada (ex.: inadimplencia)
    REJECTED = "REJECTED"  # cadastro reprovado pelo backoffice


class AddressType(StrEnum):
    """Finalidade de um endereco da empresa."""

    BILLING = "BILLING"
    SHIPPING = "SHIPPING"
