"""Regras de avatar do perfil.

O upload e feito como corpo binario (sem multipart): aceitamos somente JPG,
PNG e WebP de ate 2 MB, identificados pelos magic bytes. A URL publica usa uma
chave aleatoria por upload; ela nao e um identificador enumeravel de usuario.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.security import AuthContext
from app.modules.identity.application.errors import (
    AccountNotFoundError,
    AvatarNotFoundError,
    AvatarTooLargeError,
    InvalidAvatarError,
)
from app.modules.identity.application.ports import AccountRepository, AvatarBlob

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_ROUTE_PREFIX = "/api/v1/account/avatar"
AVATAR_CONTENT_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")


@dataclass(frozen=True, kw_only=True)
class AvatarView:
    """Resultado de upload/remocao para a camada HTTP."""

    avatar_url: str | None
    updated_at: datetime | None


def account_avatar_url(
    company_id: uuid.UUID, user_id: uuid.UUID, avatar_key: uuid.UUID
) -> str:
    """URL publica e cacheavel do avatar (chave aleatoria por upload)."""
    return f"{AVATAR_ROUTE_PREFIX}/{company_id}/{user_id}/{avatar_key}"


def validate_avatar(data: bytes) -> str:
    """Retorna o content-type detectado ou levanta erro tipado.

    O tipo declarado pelo cliente nao e confiado: a assinatura binaria decide.
    SVG/HTML e qualquer outro formato sao rejeitados.
    """
    if not data:
        raise InvalidAvatarError()
    if len(data) > MAX_AVATAR_BYTES:
        raise AvatarTooLargeError()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    raise InvalidAvatarError()


class UpdateAccountAvatar:
    """Valida e persiste a foto enviada pelo proprio usuario."""

    def __init__(self, *, repository: AccountRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext, data: bytes) -> AvatarView:
        content_type = validate_avatar(data)
        avatar_key = uuid.uuid4()
        updated_at = datetime.now(UTC)
        updated = await self._repository.set_avatar(
            company_id=auth.company_id,
            user_id=auth.user_id,
            avatar_key=avatar_key,
            content_type=content_type,
            data=data,
            updated_at=updated_at,
        )
        if not updated:
            raise AccountNotFoundError()
        return AvatarView(
            avatar_url=account_avatar_url(auth.company_id, auth.user_id, avatar_key),
            updated_at=updated_at,
        )


class RemoveAccountAvatar:
    """Remove a foto e volta para as iniciais/provedor de login."""

    def __init__(self, *, repository: AccountRepository) -> None:
        self._repository = repository

    async def execute(self, auth: AuthContext) -> AvatarView:
        removed = await self._repository.clear_avatar(
            company_id=auth.company_id, user_id=auth.user_id
        )
        if not removed:
            raise AccountNotFoundError()
        return AvatarView(avatar_url=None, updated_at=None)


class GetAccountAvatar:
    """Leitura publica (pela chave aleatoria) usada pelo <img> do frontend."""

    def __init__(self, *, repository: AccountRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, company_id: uuid.UUID, user_id: uuid.UUID, avatar_key: uuid.UUID
    ) -> AvatarBlob:
        avatar = await self._repository.get_avatar(
            company_id=company_id, user_id=user_id, avatar_key=avatar_key
        )
        if avatar is None:
            raise AvatarNotFoundError()
        return avatar
