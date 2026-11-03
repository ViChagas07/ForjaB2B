"""Testes HTTP das rotas de verificacao de telefone (com auth override)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import FastAPI

from app.application.security import AuthContext
from app.core.config import Settings
from app.interface.deps import get_current_auth
from app.interface.errors import register_exception_handlers
from app.modules.identity.application.errors import PhoneVerificationFailedError
from app.modules.identity.application.phone_verification import (
    PhoneVerificationStatus,
)
from app.modules.identity.interface.account_router import router as account_router

_AUTH = AuthContext(
    user_id=uuid.uuid4(),
    company_id=uuid.uuid4(),
    role="BUYER",
    token_id="phone-api-test",
)
_START = "/api/v1/account/phone/verification/start"
_CHECK = "/api/v1/account/phone/verification/check"
_STATUS = "/api/v1/account/phone/verification"


@dataclass
class _Start:
    calls: list[tuple[str, str | None, str]] = field(default_factory=list)

    async def execute(
        self, auth: AuthContext, *, phone_e164: str, locale: str | None, remote_ip: str
    ) -> None:
        _ = auth
        self.calls.append((phone_e164, locale, remote_ip))


@dataclass
class _Check:
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    error: Exception | None = None

    async def execute(
        self, auth: AuthContext, *, phone_e164: str, code: str, remote_ip: str
    ) -> None:
        _ = auth
        self.calls.append((phone_e164, code, remote_ip))
        if self.error is not None:
            raise self.error


@dataclass
class _Status:
    verified: bool = True
    phone_masked: str | None = "+55 ** *****-1234"

    async def execute(self, auth: AuthContext) -> PhoneVerificationStatus:
        _ = auth
        return PhoneVerificationStatus(verified=self.verified, phone_masked=self.phone_masked)


def _app(*, start: _Start, check: _Check, status: _Status) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(account_router, prefix="/api/v1")
    app.dependency_overrides[get_current_auth] = lambda: _AUTH
    app.state.settings = Settings(
        _env_file=None, environment="test", otel_enabled=False, trusted_proxy_count=0
    )
    app.state.account_phone_verification_start = start
    app.state.account_phone_verification_check = check
    app.state.account_phone_verification_status = status
    return app


async def _post(app: FastAPI, path: str, payload: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(path, json=payload)


async def test_start_normaliza_telefone_e_retorna_202() -> None:
    start = _Start()
    app = _app(start=start, check=_Check(), status=_Status())

    response = await _post(
        app,
        _START,
        {"phone": "+55 (11) 99999-1234", "locale": "pt-BR"},
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert start.calls == [("+5511999991234", "pt-BR", "127.0.0.1")]


async def test_check_falho_retorna_400_generico() -> None:
    check = _Check(error=PhoneVerificationFailedError())
    app = _app(start=_Start(), check=check, status=_Status())

    response = await _post(app, _CHECK, {"phone": "+5511999991234", "code": "000000"})

    assert response.status_code == 400
    assert response.json()["type"].endswith("phone_verification_failed")
    assert "000000" not in response.text


async def test_status_retorna_mascara() -> None:
    app = _app(start=_Start(), check=_Check(), status=_Status())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(_STATUS)

    assert response.status_code == 200
    assert response.json() == {
        "verified": True,
        "phone_masked": "+55 ** *****-1234",
    }
