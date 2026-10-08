"""Testes unitarios dos casos de uso de autenticacao (com fakes nas portas).

Cobrem: senha correta/incorreta, usuario inexistente, usuario inativo, vinculo
inativo, rotacao de refresh token e revogacao por logout, sem banco nem Redis.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.security import TokenService
from app.modules.identity.application.auth import AuthenticateUser, Logout, RefreshSession
from app.modules.identity.application.errors import (
    InvalidCredentialsError,
    RefreshTokenRejectedError,
    UserInactiveError,
)
from app.modules.identity.application.ports import (
    Membership,
    RefreshTokenPayload,
    ResolvedIdentity,
)
from app.modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus

_SECRET = "x" * 64


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str | None) -> bool:
        return password_hash == f"hashed:{password}"


class FakeResolver:
    def __init__(self, identities: dict[str, ResolvedIdentity] | None = None) -> None:
        self._identities = identities or {}

    async def resolve_by_email(self, email: str) -> ResolvedIdentity | None:
        return self._identities.get(email)


class FakeMembershipReader:
    def __init__(
        self, memberships: dict[tuple[uuid.UUID, uuid.UUID], Membership] | None = None
    ) -> None:
        self._memberships = memberships or {}

    async def get_membership(self, company_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
        return self._memberships.get((company_id, user_id))


class FakeRefreshStore:
    def __init__(self) -> None:
        self.store: dict[str, RefreshTokenPayload] = {}

    async def put(self, token_id: str, payload: RefreshTokenPayload, ttl_seconds: int) -> None:
        del ttl_seconds
        self.store[token_id] = payload

    async def get(self, token_id: str) -> RefreshTokenPayload | None:
        return self.store.get(token_id)

    async def delete(self, token_id: str) -> None:
        self.store.pop(token_id, None)


def _token_service() -> TokenService:
    return TokenService(secret_key=_SECRET, algorithm="HS256", expire_minutes=30)


def _authenticate(
    *,
    identities: dict[str, ResolvedIdentity] | None = None,
    memberships: dict[tuple[uuid.UUID, uuid.UUID], Membership] | None = None,
    refresh_store: FakeRefreshStore | None = None,
) -> tuple[AuthenticateUser, FakeRefreshStore]:
    store = refresh_store or FakeRefreshStore()
    use_case = AuthenticateUser(
        resolver=FakeResolver(identities),
        hasher=FakeHasher(),
        membership_reader=FakeMembershipReader(memberships),
        token_service=_token_service(),
        refresh_store=store,
        access_token_expire_minutes=30,
        refresh_token_expire_seconds=3600,
    )
    return use_case, store


def _identity(
    *, user_id: uuid.UUID, company_id: uuid.UUID, status: UserStatus = UserStatus.ACTIVE
) -> ResolvedIdentity:
    return ResolvedIdentity(
        user_id=user_id,
        company_id=company_id,
        status=status,
        password_hash="hashed:senha",  # noqa: S106 - hash fake, nao segredo
    )


def _membership(
    *, company_id: uuid.UUID, user_id: uuid.UUID, status: MemberStatus = MemberStatus.ACTIVE
) -> Membership:
    return Membership(
        role=MemberRole.BUYER,
        status=status,
        full_name="Comprador Teste",
        email="comprador@teste.com",
    )


async def test_login_sucesso_emite_tokens_e_perfil() -> None:
    company = uuid.uuid4()
    user = uuid.uuid4()
    use_case, store = _authenticate(
        identities={"c@t.com": _identity(user_id=user, company_id=company)},
        memberships={(company, user): _membership(company_id=company, user_id=user)},
    )
    result = await use_case.login("c@t.com", "senha")
    assert result.role == "BUYER"
    assert result.email == "comprador@teste.com"
    assert result.access_token and result.refresh_token
    assert len(store.store) == 1
    decoded = _token_service().decode_access_token(result.access_token)
    assert decoded.company_id == company
    assert decoded.user_id == user


async def test_login_senha_incorreta() -> None:
    company = uuid.uuid4()
    user = uuid.uuid4()
    use_case, _ = _authenticate(identities={"c@t.com": _identity(user_id=user, company_id=company)})
    with pytest.raises(InvalidCredentialsError):
        await use_case.login("c@t.com", "senha-errada")


async def test_login_usuario_inexistente() -> None:
    use_case, _ = _authenticate(identities={})
    with pytest.raises(InvalidCredentialsError):
        await use_case.login("ninguem@t.com", "qualquer")


async def test_login_usuario_inativo() -> None:
    company = uuid.uuid4()
    user = uuid.uuid4()
    use_case, _ = _authenticate(
        identities={
            "c@t.com": _identity(user_id=user, company_id=company, status=UserStatus.SUSPENDED)
        }
    )
    with pytest.raises(UserInactiveError):
        await use_case.login("c@t.com", "senha")


async def test_login_vinculo_inativo() -> None:
    company = uuid.uuid4()
    user = uuid.uuid4()
    use_case, _ = _authenticate(
        identities={"c@t.com": _identity(user_id=user, company_id=company)},
        memberships={
            (company, user): _membership(
                company_id=company, user_id=user, status=MemberStatus.DISABLED
            )
        },
    )
    with pytest.raises(UserInactiveError):
        await use_case.login("c@t.com", "senha")


async def test_refresh_rotaciona_token_e_invalida_antigo() -> None:
    company = uuid.uuid4()
    user = uuid.uuid4()
    store = FakeRefreshStore()
    use_case, _ = _authenticate(
        identities={"c@t.com": _identity(user_id=user, company_id=company)},
        memberships={(company, user): _membership(company_id=company, user_id=user)},
        refresh_store=store,
    )
    result = await use_case.login("c@t.com", "senha")
    old_refresh = result.refresh_token
    assert old_refresh in store.store

    refresh_use_case = RefreshSession(
        refresh_store=store,
        token_service=_token_service(),
        access_token_expire_minutes=30,
        refresh_token_expire_seconds=3600,
    )
    refreshed = await refresh_use_case.refresh(old_refresh)
    assert refreshed.refresh_token != old_refresh
    assert old_refresh not in store.store
    assert refreshed.refresh_token in store.store


async def test_refresh_token_invalido() -> None:
    store = FakeRefreshStore()
    use_case = RefreshSession(
        refresh_store=store,
        token_service=_token_service(),
        access_token_expire_minutes=30,
        refresh_token_expire_seconds=3600,
    )
    with pytest.raises(RefreshTokenRejectedError):
        await use_case.refresh("token-desconhecido")


async def test_logout_revoga_refresh_token() -> None:
    store = FakeRefreshStore()
    payload = RefreshTokenPayload(user_id=uuid.uuid4(), company_id=uuid.uuid4(), role="BUYER")
    await store.put("refresh-id", payload, 3600)
    assert await store.get("refresh-id") is not None

    use_case = Logout(refresh_store=store)
    await use_case.logout("refresh-id")
    assert await store.get("refresh-id") is None
