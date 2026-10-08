"""Contexto de tenant (porta de entrada de identidade).

Na Fase 0 a autenticacao ainda nao existe: esta porta apenas RECEBE
`company_id`/`user_id` ja derivados de uma identidade autenticada (fase
futura). O contexto alimenta as GUCs transacionais do PostgreSQL (RLS).

IMPORTANTE: definir o contexto de tenant NAO autentica nem autoriza. A
funcao PostgreSQL `app.set_tenant_context` e apenas o mecanismo de
transporte do contexto para as policies RLS.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TenantContext:
    """Identidade de tenant ja autenticada, pronta para o contexto RLS."""

    company_id: uuid.UUID
    user_id: uuid.UUID | None = None


class TenantContextProvider(Protocol):
    """Origem do tenant da requisicao (implementada pela interface, futura auth)."""

    def current(self) -> TenantContext | None:
        """Contexto autenticado da requisicao corrente, ou None (anonimo)."""
        ...
