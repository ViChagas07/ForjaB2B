"""Testes da dependencia de access token com checagem de epoca (cep)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI

from app.application.security import (
    AuthContext,
    CredentialEpochUnavailableError,
    TokenService,
)
from app.core.config import Settings
from app.interface.deps import get_current_auth
from app.interface.errors import register_exception_handlers


class _Epoch:
    def __init__(self, epoch: int = 0, *, error: Exception | None = None) -> None:
        self.epoch = epoch
        self.error = error

    async def resolve(self, *, user_id: uuid.UUID, company_id: uuid.UUID) -> int:
        _ = (user_id, company_id)
        if self.error is not None:
            raise self.error
        return self.epoch


def _settings() -> Settings:
    return Settings(_env_file=None, environment="test", otel_enabled=False)


def _app(epoch: _Epoch) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/me")
    async def me(
        auth: Annotated[AuthContext, Depends(get_current_auth)],
    ) -> dict[str, object]:
        return {"user_id": str(auth.user_id), "cep": auth.credential_epoch}

    app.state.settings = _settings()
    app.state.credential_epoch = epoch
    return app


def _token(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    credential_epoch: int,
    include_cep: bool = True,
) -> str:
    service = TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )
    if include_cep:
        return service.issue_access_token(
            AuthContext(
                user_id=user_id,
                company_id=company_id,
                role="BUYER",
                token_id=uuid.uuid4().hex,
                credential_epoch=credential_epoch,
            )
        )
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "company_id": str(company_id),
            "role": "BUYER",
            "type": "access",
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + timedelta(minutes=30),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def _get(app: FastAPI, token: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get("/me", headers={"Authorization": f"Bearer {token}"})


async def test_epoca_atual_aceita_token_com_cep_igual() -> None:
    settings = _settings()
    user_id, company_id = uuid.uuid4(), uuid.uuid4()
    response = await _get(
        _app(_Epoch(epoch=2)),
        _token(settings, user_id=user_id, company_id=company_id, credential_epoch=2),
    )
    assert response.status_code == 200
    assert response.json()["cep"] == 2


async def test_epoca_anterior_rejeita_token_com_401() -> None:
    settings = _settings()
    response = await _get(
        _app(_Epoch(epoch=2)),
        _token(settings, user_id=uuid.uuid4(), company_id=uuid.uuid4(), credential_epoch=1),
    )
    assert response.status_code == 401
    assert response.json()["type"].endswith("invalid_token")


async def test_token_legado_sem_cep_e_epoca_zero() -> None:
    settings = _settings()
    user_id, company_id = uuid.uuid4(), uuid.uuid4()
    token = _token(
        settings,
        user_id=user_id,
        company_id=company_id,
        credential_epoch=0,
        include_cep=False,
    )

    accepted = await _get(_app(_Epoch(epoch=0)), token)
    rejected = await _get(_app(_Epoch(epoch=1)), token)

    assert accepted.status_code == 200
    assert accepted.json()["cep"] == 0
    assert rejected.status_code == 401


async def test_epoca_indisponivel_falha_fechado_503() -> None:
    settings = _settings()
    response = await _get(
        _app(_Epoch(error=CredentialEpochUnavailableError())),
        _token(settings, user_id=uuid.uuid4(), company_id=uuid.uuid4(), credential_epoch=0),
    )
    assert response.status_code == 503
    assert response.json()["type"].endswith("credential_epoch_unavailable")


async def test_sem_token_retorna_401() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(_Epoch())), base_url="http://test"
    ) as client:
        response = await client.get("/me")
    assert response.status_code == 401


@pytest.mark.parametrize("cep", ["1", -1, True, 1.5])
async def test_cep_invalido_nao_chega_ao_resolver(cep: object) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "company_id": str(uuid.uuid4()),
            "role": "BUYER",
            "type": "access",
            "jti": uuid.uuid4().hex,
            "cep": cep,
            "iat": now,
            "exp": now + timedelta(minutes=30),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = await _get(_app(_Epoch(epoch=0)), token)
    assert response.status_code == 401
