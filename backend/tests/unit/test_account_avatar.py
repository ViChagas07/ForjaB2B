"""Avatar do perfil: validacao de bytes, persistencia e URL publica."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from app.application.security import AuthContext
from app.modules.identity.application.avatar import (
    AVATAR_ROUTE_PREFIX,
    MAX_AVATAR_BYTES,
    GetAccountAvatar,
    RemoveAccountAvatar,
    UpdateAccountAvatar,
    account_avatar_url,
    validate_avatar,
)
from app.modules.identity.application.errors import (
    AccountNotFoundError,
    AvatarNotFoundError,
    AvatarTooLargeError,
    InvalidAvatarError,
)
from app.modules.identity.application.ports import AccountRepository, AvatarBlob

_COMPANY = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_USER = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_AUTH = AuthContext(
    user_id=_USER,
    company_id=_COMPANY,
    role="BUYER",
    token_id="avatar-test",
)
_PNG = b"\x89PNG\r\n\x1a\n" + b"conteudo"
_JPEG = b"\xff\xd8\xff\xe0" + b"conteudo"
_WEBP = b"RIFF" + (4).to_bytes(4, "little") + b"WEBP" + b"conteudo"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (_PNG, "image/png"),
        (_JPEG, "image/jpeg"),
        (_WEBP, "image/webp"),
    ],
)
def test_detecta_tipos_permitidos_pelos_magic_bytes(data: bytes, expected: str) -> None:
    assert validate_avatar(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"<html><script>alert(1)</script></html>",
        b"GIF89a",
    ],
)
def test_rejeita_formatos_nao_suportados(data: bytes) -> None:
    with pytest.raises(InvalidAvatarError):
        validate_avatar(data)


def test_rejeita_arquivo_maior_que_2mb() -> None:
    with pytest.raises(AvatarTooLargeError):
        validate_avatar(_PNG + b"x" * MAX_AVATAR_BYTES)


class FakeAvatarRepository:
    def __init__(self, *, exists: bool = True, avatar: AvatarBlob | None = None) -> None:
        self.exists = exists
        self.avatar = avatar
        self.saved: dict[str, object] | None = None
        self.cleared = False

    async def set_avatar(self, **kwargs: object) -> bool:
        self.saved = kwargs
        return self.exists

    async def clear_avatar(self, **kwargs: object) -> bool:
        self.cleared = True
        return self.exists

    async def get_avatar(self, **kwargs: object) -> AvatarBlob | None:
        return self.avatar


def _repository(fake: FakeAvatarRepository) -> AccountRepository:
    return cast(AccountRepository, fake)


async def test_upload_salva_bytes_e_devolve_url_com_chave_aleatoria() -> None:
    repository = FakeAvatarRepository()

    view = await UpdateAccountAvatar(repository=_repository(repository)).execute(_AUTH, _PNG)

    assert view.avatar_url is not None
    assert view.avatar_url.startswith(f"{AVATAR_ROUTE_PREFIX}/{_COMPANY}/{_USER}/")
    assert view.updated_at is not None
    assert repository.saved is not None
    assert repository.saved["content_type"] == "image/png"
    assert repository.saved["data"] == _PNG
    assert str(repository.saved["avatar_key"]) in view.avatar_url


async def test_upload_invalido_nao_chega_ao_banco() -> None:
    repository = FakeAvatarRepository()

    with pytest.raises(InvalidAvatarError):
        await UpdateAccountAvatar(repository=_repository(repository)).execute(
            _AUTH, b"<html>nao e imagem</html>"
        )

    assert repository.saved is None


async def test_upload_de_usuario_ausente_404() -> None:
    with pytest.raises(AccountNotFoundError):
        await UpdateAccountAvatar(
            repository=_repository(FakeAvatarRepository(exists=False))
        ).execute(_AUTH, _PNG)


async def test_remocao_de_avatar() -> None:
    repository = FakeAvatarRepository()

    view = await RemoveAccountAvatar(repository=_repository(repository)).execute(_AUTH)

    assert view.avatar_url is None
    assert view.updated_at is None
    assert repository.cleared is True


async def test_leitura_publica_por_chave() -> None:
    updated_at = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    blob = AvatarBlob(content_type="image/png", data=_PNG, updated_at=updated_at)
    use_case = GetAccountAvatar(repository=_repository(FakeAvatarRepository(avatar=blob)))

    result = await use_case.execute(
        company_id=_COMPANY, user_id=_USER, avatar_key=uuid.uuid4()
    )

    assert result == blob


async def test_leitura_de_avatar_inexistente_404() -> None:
    use_case = GetAccountAvatar(repository=_repository(FakeAvatarRepository(avatar=None)))

    with pytest.raises(AvatarNotFoundError):
        await use_case.execute(company_id=_COMPANY, user_id=_USER, avatar_key=uuid.uuid4())


def test_url_publica_e_estavel() -> None:
    key = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    assert (
        account_avatar_url(_COMPANY, _USER, key)
        == f"/api/v1/account/avatar/{_COMPANY}/{_USER}/{key}"
    )
