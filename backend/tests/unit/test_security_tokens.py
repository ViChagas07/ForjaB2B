"""Testes unitarios do TokenService (JWT de acesso) e RBAC (require_role)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.application.security import (
    AuthContext,
    AuthorizationError,
    ExpiredTokenError,
    InvalidTokenError,
    TokenService,
    require_role,
)

_SECRET = "x" * 64


def _service(*, expire_minutes: int = 30) -> TokenService:
    return TokenService(secret_key=_SECRET, algorithm="HS256", expire_minutes=expire_minutes)


def _auth(role: str = "BUYER") -> AuthContext:
    return AuthContext(
        user_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        role=role,
        token_id=uuid.uuid4().hex,
    )


def test_issue_decode_roundtrip() -> None:
    svc = _service()
    auth = _auth(role="APPROVER")
    decoded = svc.decode_access_token(svc.issue_access_token(auth))
    assert decoded == auth


def test_token_assinado_com_outra_chave_rejeitado() -> None:
    svc = _service()
    token = svc.issue_access_token(_auth())
    other = TokenService(secret_key="y" * 64, algorithm="HS256", expire_minutes=30)
    with pytest.raises(InvalidTokenError):
        other.decode_access_token(token)


def test_token_expirado() -> None:
    svc = _service(expire_minutes=-1)
    token = svc.issue_access_token(_auth())
    with pytest.raises(ExpiredTokenError):
        svc.decode_access_token(token)


def test_token_tipo_refresh_rejeitado_como_acesso() -> None:
    svc = _service()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "role": "BUYER",
        "type": "refresh",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    token = jwt.encode(payload, _SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        svc.decode_access_token(token)


def test_token_sem_claims_obrigatorias_rejeitado() -> None:
    svc = _service()
    token = jwt.encode({"foo": "bar"}, _SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        svc.decode_access_token(token)


def test_token_com_sub_invalido_rejeitado() -> None:
    svc = _service()
    now = datetime.now(UTC)
    payload = {
        "sub": "nao-e-uuid",
        "company_id": str(uuid.uuid4()),
        "role": "BUYER",
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }
    token = jwt.encode(payload, _SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        svc.decode_access_token(token)


def test_require_role_permitido() -> None:
    require_role(_auth(role="ADMIN"), "ADMIN", "APPROVER")


def test_require_role_insuficiente_negado() -> None:
    with pytest.raises(AuthorizationError):
        require_role(_auth(role="BUYER"), "ADMIN")
