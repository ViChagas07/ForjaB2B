"""Seguranca transversal de aplicacao (Fase 2): identidade autenticada e RBAC.

Este modulo vive na camada de aplicacao compartilhada para que qualquer bounded
context (que nao pode importar outro modulo) consiga ler a identidade autenticada
e aplicar autorizacao sem acoplar-se ao modulo identity.

- ``AuthContext`` e o principal (user_id, company_id, role) derivado do token.
- ``TokenService`` assina/valida JWTs de acesso (HS256). Claims minimas.
- ``require_role``/``require_any_role`` aplicam RBAC no backend.

Nenhuma confianca em claims fornecidas pelo cliente: o unico token aceito e
aquele assinado com ``secret_key`` do servidor e validado aqui.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.core.errors import AppError

_ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - marcador de tipo de claim, nao segredo


class InvalidTokenError(AppError):
    """Token ausente, malformado, assinatura invalida ou claims invalidas."""

    status_code = 401
    title = "Unauthorized"
    code = "invalid_token"


class ExpiredTokenError(AppError):
    """Token de acesso expirado."""

    status_code = 401
    title = "Unauthorized"
    code = "token_expired"


class AuthorizationError(AppError):
    """Identidade autenticada porem sem permissao (403)."""

    status_code = 403
    title = "Forbidden"
    code = "forbidden"


@dataclass(frozen=True, kw_only=True)
class AuthContext:
    """Principal autenticado derivado de um token de acesso valido.

    ``role`` e um dos valores de ``MemberRole`` (identity.domain.enums), mas
    representado como ``str`` aqui para evitar acoplamento entre o dominio
    compartilhado e o vocabulario de um modulo especifico.
    """

    user_id: uuid.UUID
    company_id: uuid.UUID
    role: str
    token_id: str


def require_role(auth: AuthContext, *allowed_roles: str) -> None:
    """Falha com 403 quando o papel do principal nao esta entre os permitidos."""
    if auth.role not in allowed_roles:
        raise AuthorizationError()


def require_any_role(auth: AuthContext, allowed_roles: set[str]) -> None:
    """Variante por conjunto (para chamadas dinamicas)."""
    if auth.role not in allowed_roles:
        raise AuthorizationError()


class TokenService:
    """Emissao e validacao de JWTs de acesso (HS256, claims minimas)."""

    def __init__(self, *, secret_key: str, algorithm: str, expire_minutes: int) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def issue_access_token(self, auth: AuthContext) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(auth.user_id),
            "company_id": str(auth.company_id),
            "role": auth.role,
            "type": _ACCESS_TOKEN_TYPE,
            "jti": auth.token_id,
            "iat": now,
            "exp": now + timedelta(minutes=self._expire_minutes),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> AuthContext:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["sub", "company_id", "role", "type", "jti", "exp"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError() from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError() from exc

        if payload.get("type") != _ACCESS_TOKEN_TYPE:
            raise InvalidTokenError()
        try:
            user_id = uuid.UUID(str(payload["sub"]))
            company_id = uuid.UUID(str(payload["company_id"]))
        except (ValueError, AttributeError, TypeError) as exc:
            raise InvalidTokenError() from exc
        role = payload.get("role")
        token_id = payload.get("jti")
        if not isinstance(role, str) or not role or not isinstance(token_id, str) or not token_id:
            raise InvalidTokenError()
        return AuthContext(user_id=user_id, company_id=company_id, role=role, token_id=token_id)
