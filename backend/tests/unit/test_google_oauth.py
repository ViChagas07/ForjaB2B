"""Testes unitarios do fluxo OAuth Google (use cases, com fakes deterministicos).

O callback nao devolve tokens na URL: devolve um exchange code de uso unico que
e trocado no endpoint de troca (JSON). Nenhum token/secret/identity em URL.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from app.application.security import TokenService
from app.core.config import Settings
from app.modules.identity.application.errors import (
    OAuthCodeError,
    OAuthEmailNotVerifiedError,
    OAuthExchangeError,
    OAuthStateError,
    UserInactiveError,
)
from app.modules.identity.application.google_oauth import (
    BuildGoogleAuthorizationUrl,
    CompleteGoogleOAuth,
    ExchangeOAuthCode,
)
from app.modules.identity.application.ports import (
    GoogleUserInfo,
    Membership,
    OAuthExchange,
    RefreshTokenPayload,
    ResolvedIdentity,
)
from app.modules.identity.domain.enums import MemberRole, MemberStatus, UserStatus

_CLIENT_ID = "client-id-123"
_CLIENT_SECRET = "client-secret-456"
_REDIRECT_URI = "https://api.example.com/api/v1/auth/google/callback"
_SECRET_KEY = "test_secret_key_for_jwt_signing_min_32_bytes"


class FakeGoogleClient:
    def __init__(
        self, userinfo: GoogleUserInfo | None = None, error: Exception | None = None
    ) -> None:
        self._userinfo = userinfo
        self._error = error

    async def exchange_authorization_code(self, code: str) -> GoogleUserInfo:
        if self._error is not None:
            raise self._error
        assert self._userinfo is not None
        return self._userinfo


class FakeStateStore:
    def __init__(self, valid: bool = True) -> None:
        self._valid = valid
        self.states: list[str] = []

    async def put(self, state: str, ttl_seconds: int) -> None:
        self.states.append(state)

    async def consume(self, state: str) -> bool:
        return self._valid


class FakeExchangeCodeStore:
    def __init__(self) -> None:
        self.codes: dict[str, OAuthExchange] = {}

    async def put(self, code: str, payload: OAuthExchange, ttl_seconds: int) -> None:
        self.codes[code] = payload

    async def consume(self, code: str) -> OAuthExchange | None:
        return self.codes.pop(code, None)


class FakeExternalIdentityRepository:
    def __init__(self) -> None:
        self.links: list[dict[str, object]] = []
        self.error: Exception | None = None

    async def link(self, **kwargs: object) -> None:
        if self.error is not None:
            raise self.error
        self.links.append(kwargs)


class FakeResolver:
    def __init__(self, identity: ResolvedIdentity | None) -> None:
        self._identity = identity

    async def resolve_by_email(self, email: str) -> ResolvedIdentity | None:
        return self._identity


class FakeMembershipReader:
    def __init__(self, membership: Membership | None) -> None:
        self._membership = membership

    async def get_membership(self, company_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
        return self._membership


class FakeRefreshStore:
    def __init__(self) -> None:
        self.tokens: dict[str, RefreshTokenPayload] = {}

    async def put(self, token: str, payload: RefreshTokenPayload, ttl_seconds: int) -> None:
        self.tokens[token] = payload

    async def get(self, token: str) -> RefreshTokenPayload | None:
        return self.tokens.get(token)

    async def delete(self, token: str) -> None:
        self.tokens.pop(token, None)


def _userinfo() -> GoogleUserInfo:
    return GoogleUserInfo(
        subject="google-sub-1", email="buyer@empresa.com", email_verified=True, name="Buyer"
    )


def _identity() -> ResolvedIdentity:
    return ResolvedIdentity(
        user_id=uuid.UUID("aaaa0000-0000-4000-8000-000000000001"),
        company_id=uuid.UUID("aaaa0000-0000-4000-8000-000000000002"),
        status=UserStatus.ACTIVE,
        password_hash="x",  # noqa: S106 - dado de teste, nao segredo real
    )


def _membership() -> Membership:
    return Membership(
        role=MemberRole.BUYER,
        status=MemberStatus.ACTIVE,
        full_name="Buyer",
        email="buyer@empresa.com",
    )


def _token_service() -> TokenService:
    return TokenService(secret_key=_SECRET_KEY, algorithm="HS256", expire_minutes=30)


def _complete_usecase(**overrides: Any) -> CompleteGoogleOAuth:
    args: dict[str, Any] = {
        "google_client": FakeGoogleClient(userinfo=_userinfo()),
        "state_store": FakeStateStore(),
        "exchange_code_store": FakeExchangeCodeStore(),
        "resolver": FakeResolver(_identity()),
        "external_identity_repository": FakeExternalIdentityRepository(),
        "membership_reader": FakeMembershipReader(_membership()),
        "token_service": _token_service(),
        "refresh_store": FakeRefreshStore(),
        "access_token_expire_minutes": 30,
        "refresh_token_expire_seconds": 7 * 24 * 3600,
    }
    args.update(overrides)
    return CompleteGoogleOAuth(**args)


async def test_gera_redirect_com_state_e_sem_secret() -> None:
    store = FakeStateStore()
    use_case = BuildGoogleAuthorizationUrl(
        client_id=_CLIENT_ID, redirect_uri=_REDIRECT_URI, state_store=store
    )
    url = await use_case.build()

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == [_CLIENT_ID]
    assert query["redirect_uri"] == [_REDIRECT_URI]
    assert query["response_type"] == ["code"]
    assert "state" in query and len(query["state"][0]) > 0
    assert _CLIENT_SECRET not in url
    assert store.states == query["state"]


async def test_callback_valido_gera_exchange_code_sem_token_na_url() -> None:
    links = FakeExternalIdentityRepository()
    exchange_store = FakeExchangeCodeStore()
    refresh_store = FakeRefreshStore()
    use_case = _complete_usecase(
        external_identity_repository=links,
        exchange_code_store=exchange_store,
        refresh_store=refresh_store,
    )
    result = await use_case.complete(code="code-ok", state="state-ok")

    assert result.status == "authenticated"
    assert result.exchange_code
    # Nenhum token/secret aparece no resultado (so o exchange code opaco).
    assert _CLIENT_SECRET not in result.exchange_code

    # O exchange code troca para a sessao (com tokens) via o store.
    payload = await exchange_store.consume(result.exchange_code)
    assert payload is not None
    assert payload.status == "authenticated"
    assert payload.access_token
    assert payload.refresh_token
    assert payload.email == "buyer@empresa.com"
    assert payload.role == "BUYER"
    assert len(links.links) == 1
    assert len(refresh_store.tokens) == 1


async def test_exchange_code_uso_unico() -> None:
    exchange_store = FakeExchangeCodeStore()
    use_case = _complete_usecase(exchange_code_store=exchange_store)
    result = await use_case.complete(code="code", state="state")

    first = await exchange_store.consume(result.exchange_code)
    second = await exchange_store.consume(result.exchange_code)
    assert first is not None
    assert second is None


async def test_exchange_code_invalido_ou_reutilizado_erro() -> None:
    exchange = ExchangeOAuthCode(store=FakeExchangeCodeStore())
    with pytest.raises(OAuthExchangeError):
        await exchange.exchange("codigo-nao-existe")


async def test_callback_state_invalido() -> None:
    use_case = _complete_usecase(state_store=FakeStateStore(valid=False))
    with pytest.raises(OAuthStateError):
        await use_case.complete(code="code", state="bad-state")


async def test_callback_code_invalido() -> None:
    use_case = _complete_usecase(google_client=FakeGoogleClient(error=RuntimeError("bad code")))
    with pytest.raises(OAuthCodeError):
        await use_case.complete(code="bad-code", state="state")


async def test_callback_email_nao_verificado() -> None:
    userinfo = GoogleUserInfo(
        subject="sub", email="buyer@empresa.com", email_verified=False, name="Buyer"
    )
    use_case = _complete_usecase(google_client=FakeGoogleClient(userinfo=userinfo))
    with pytest.raises(OAuthEmailNotVerifiedError):
        await use_case.complete(code="code", state="state")


async def test_callback_conta_inexistente_vai_para_onboarding() -> None:
    exchange_store = FakeExchangeCodeStore()
    use_case = _complete_usecase(resolver=FakeResolver(None), exchange_code_store=exchange_store)
    result = await use_case.complete(code="code", state="state")

    assert result.status == "onboarding"
    assert result.exchange_code
    payload = await exchange_store.consume(result.exchange_code)
    assert payload is not None
    assert payload.status == "onboarding"
    assert payload.access_token is None
    assert payload.email == "buyer@empresa.com"


async def test_callback_usuario_inativo() -> None:
    identity = _identity()
    inactive = ResolvedIdentity(
        user_id=identity.user_id,
        company_id=identity.company_id,
        status=UserStatus.SUSPENDED,
        password_hash=identity.password_hash,
    )
    use_case = _complete_usecase(resolver=FakeResolver(inactive))
    with pytest.raises(UserInactiveError):
        await use_case.complete(code="code", state="state")


async def test_callback_nao_expoe_client_secret() -> None:
    exchange_store = FakeExchangeCodeStore()
    use_case = _complete_usecase(exchange_code_store=exchange_store)
    result = await use_case.complete(code="code", state="state")

    payload = await exchange_store.consume(result.exchange_code)
    assert payload is not None
    assert _CLIENT_SECRET not in (payload.access_token or "")
    assert _CLIENT_SECRET not in (payload.refresh_token or "")


def test_settings_oauth_enabled() -> None:
    assert Settings().google_oauth_enabled is False
    enabled = Settings(
        google_client_id="id",
        google_client_secret="secret",  # noqa: S106 - valor de teste, nao segredo real
        google_redirect_uri="https://x/cb",
        google_oauth_frontend_redirect="https://x/f",
    )
    assert enabled.google_oauth_enabled is True
