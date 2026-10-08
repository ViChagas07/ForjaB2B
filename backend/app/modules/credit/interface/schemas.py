"""Schemas HTTP do contexto de credito (somente leitura de conta/ledger)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CreditAccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: uuid.UUID
    credit_limit: Decimal
    used: Decimal
    available: Decimal
    currency: str


class CreditEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    entry_type: str
    amount: Decimal
    reference_type: str | None
    reference_id: uuid.UUID | None
    description: str | None
    created_at: datetime
