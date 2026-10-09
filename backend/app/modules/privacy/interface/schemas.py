"""Schemas HTTP do contexto de privacidade (LGPD)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.privacy.domain.enums import ConsentAction, ConsentPurpose


class ConsentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str
    action: str
    version: str
    consented_at: datetime


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    resource: str
    resource_id: uuid.UUID
    created_at: datetime


class PersonalDataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    company_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    status: str
    role: str | None
    email_verified_at: datetime | None
    last_login_at: datetime | None
    consents: list[ConsentResponse]
    audit_entries: list[AuditEntryResponse]


class RectifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ConsentPurpose
    action: ConsentAction
    version: str = Field(min_length=1, max_length=20)
    document_hash: str = Field(min_length=1, max_length=64)
