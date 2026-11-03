"""Testes HTTP da recuperacao de conta (request, verify e reset)."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI
from fastapi.routing import APIRoute
from structlog.testing import capture_logs

from app.core.config import Settings
from app.core.errors import RateLimitExceededError, ServiceUnavailableError
from app.infrastructure.cache.redis import close_redis_client
from app.interface.errors import register_exception_handlers
from app.main import create_app
from app.modules.identity.application.errors import (
    AntiBotVerificationError,
    PasswordRecoveryCodeError,
    PasswordResetTokenError,
)
from app.modules.identity.application.password_recovery import (
    PasswordRecoveryCommand,
    PasswordRecoveryVerified,
    RequestPasswordRecovery,
    ResetPassword,
    VerifyPasswordRecoveryCode,
)
from app.modules.identity.domain.errors import WeakPasswordError
from app.modules.identity.interface.password_recovery_router import (
    router as password_recovery_router,
)

_ENDPOINT = "/api/v1/auth/password-recovery/request"
_VERIFY_ENDPOINT = "/api/v1/auth/password-recovery/verify"
_RESET_ENDPOINT = "/api/v1/auth/password-recovery/reset"
_TOKEN = "turnstile-token-123"


@dataclass
class _RecordingUseCase:
    commands: list[PasswordRecoveryCommand] = field(default_factory=list)
    error: Exception | None = None

    async def execute(self, command: PasswordRecoveryCommand) -> None:
        self.commands.append(command)
        if self.error is not None:
            raise self.error


@dataclass
class _VerifyUseCase:
    calls: list[tuple[str | None, str | None, str, str]] = field(default_factory=list)
    error: Exception | None = None
    reset_token: str = "reset-token-opaco"

    async def execute(
        self,
        *,
        email: str | None = None,
        phone_e164: str | None = None,
        code: str,
        remote_ip: str,
    ) -> PasswordRecoveryVerified:
        self.calls.append((email, phone_e164, code, remote_ip))
        if self.error is not None:
            raise self.error
        return PasswordRecoveryVerified(reset_token=self.reset_token, expires_in=600)


@dataclass
class _ResetUseCase:
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    error: Exception | None = None

    async def execute(self, *, reset_token: str, new_password: str, remote_ip: str) -> None:
        self.calls.append((reset_token, new_password, remote_ip))
        if self.error is not None:
            raise self.error


def _settings(*, enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        otel_enabled=False,
        password_recovery_enabled=enabled,
        trusted_proxy_count=0,
    )


def _app(
    usecase: _RecordingUseCase,
    *,
    verify: _VerifyUseCase | None = None,
    reset: _ResetUseCase | None = None,
    enabled: bool = True,
) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(password_recovery_router, prefix="/api/v1")
    app.state.settings = _settings(enabled=enabled)
    app.state.password_recovery_request = usecase
    app.state.password_recovery_verify = verify or _VerifyUseCase()
    app.state.password_recovery_reset = reset or _ResetUseCase()
    return app


async def _post(
    app: FastAPI, payload: dict[str, object], *, path: str = _ENDPOINT
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(path, json=payload)


def _payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "email": "user@example.com",
        "turnstile_token": _TOKEN,
        "locale": "pt-BR",
    }
    values.update(overrides)
    return values


async def test_xor_rejeita_ambos_e_nenhum() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase)

    both = await _post(
        app,
        {
            "email": "user@example.com",
            "phone": "+5511999999999",
            "turnstile_token": _TOKEN,
        },
    )
    neither = await _post(app, {"turnstile_token": _TOKEN})

    assert both.status_code == 422
    assert neither.status_code == 422
    assert both.headers["content-type"].startswith("application/problem+json")
    assert usecase.commands == []


async def test_email_e_normalizado_e_resposta_e_generica() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase)

    response = await _post(app, _payload(email="  User@Example.COM  "))

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert usecase.commands == [
        PasswordRecoveryCommand(
            email="user@example.com",
            phone_e164=None,
            turnstile_token=_TOKEN,
            locale="pt-BR",
            remote_ip="127.0.0.1",
        )
    ]


async def test_telefone_brasileiro_e_normalizado_para_e164() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase)

    response = await _post(
        app,
        _payload(email=None, phone="+55 (11) 99999-9999"),
    )

    assert response.status_code == 202
    assert usecase.commands[0].phone_e164 == "+5511999999999"
    assert usecase.commands[0].email is None


async def test_telefone_internacional_valido_em_e164() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase)

    response = await _post(app, _payload(email=None, phone="+1 (415) 555-2671"))

    assert response.status_code == 202
    assert usecase.commands[0].phone_e164 == "+14155552671"


async def test_telefones_invalidos_retornam_422() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase)

    for phone in (
        "11999999999",
        "+55 10 99999-9999",
        "+55 11 9999",
        "+999",
        "+55 11 99999-9999x",
    ):
        response = await _post(app, _payload(email=None, phone=phone))
        assert response.status_code == 422, phone
    assert usecase.commands == []


async def test_email_invalido_e_locale_invalido_retornam_422() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase)

    invalid_email = await _post(app, _payload(email="not-an-email"))
    invalid_locale = await _post(app, _payload(locale="pt-BR-extra"))

    assert invalid_email.status_code == 422
    assert invalid_locale.status_code == 422
    assert usecase.commands == []


async def test_resposta_generica_identica_em_canais_diferentes() -> None:
    email_response = await _post(_app(_RecordingUseCase()), _payload())
    phone_response = await _post(
        _app(_RecordingUseCase()), _payload(email=None, phone="+5511988887777")
    )

    assert email_response.status_code == phone_response.status_code == 202
    assert email_response.content == phone_response.content


async def test_feature_desligada_retorna_404_generico() -> None:
    usecase = _RecordingUseCase()
    app = _app(usecase, enabled=False)

    response = await _post(app, _payload())

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["detail"] == "Not Found"
    assert usecase.commands == []


async def test_antibot_falho_retorna_400_generico() -> None:
    usecase = _RecordingUseCase(error=AntiBotVerificationError())
    response = await _post(_app(usecase), _payload(email="pii@example.com"))

    body = response.json()
    assert response.status_code == 400
    assert body["type"].endswith("antibot_verification_failed")
    assert "pii@example.com" not in response.text
    assert "cloudflare" not in response.text.lower()
    assert _TOKEN not in response.text


async def test_rate_limit_retorna_429_com_retry_after() -> None:
    usecase = _RecordingUseCase(
        error=RateLimitExceededError(
            retry_after_seconds=7,
            limit=3,
            remaining=0,
            reset_after_seconds=7,
        )
    )
    response = await _post(_app(usecase), _payload())

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.headers["RateLimit-Limit"] == "3"
    assert response.json()["type"].endswith("rate_limit_exceeded")


async def test_redis_indisponivel_retorna_503_generico() -> None:
    usecase = _RecordingUseCase(
        error=ServiceUnavailableError("Servico temporariamente indisponivel.")
    )
    response = await _post(_app(usecase), _payload())

    assert response.status_code == 503
    assert response.json()["type"].endswith("service_unavailable")
    assert "redis" not in response.text.lower()


async def test_logs_nao_contem_email_telefone_nem_token() -> None:
    usecase = _RecordingUseCase(error=AntiBotVerificationError())
    app = _app(usecase)

    with capture_logs() as logs:
        await _post(app, _payload(email="pii-log@example.com"))
        await _post(
            app,
            _payload(email=None, phone="+5511977776666", turnstile_token="tok-log-secret"),
        )

    rendered = str(logs)
    assert "pii-log@example.com" not in rendered
    assert "+5511977776666" not in rendered
    assert "tok-log-secret" not in rendered


async def test_create_app_registra_rota_e_caso_de_uso() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            otel_enabled=False,
            password_recovery_enabled=True,
            rate_limit_enabled=False,
            turnstile_secret_key="test-turnstile-secret",
        )
    )
    try:
        paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
        assert _ENDPOINT in paths
        assert _VERIFY_ENDPOINT in paths
        assert _RESET_ENDPOINT in paths
        assert isinstance(app.state.password_recovery_request, RequestPasswordRecovery)
        assert isinstance(app.state.password_recovery_verify, VerifyPasswordRecoveryCode)
        assert isinstance(app.state.password_recovery_reset, ResetPassword)
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


async def test_create_app_desabilitado_nao_registra_rota() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            otel_enabled=False,
            password_recovery_enabled=False,
            rate_limit_enabled=False,
        )
    )
    try:
        paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
        assert _ENDPOINT not in paths
        response = await _post(app, _payload())
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["detail"] == "Not Found"
    finally:
        await app.state.db_engine.dispose()
        await close_redis_client(app.state.redis_client)


async def test_verify_devolve_reset_token_e_normaliza_email() -> None:
    verify = _VerifyUseCase()
    app = _app(_RecordingUseCase(), verify=verify)

    response = await _post(
        app,
        {"email": "  User@Example.COM  ", "code": "123456"},
        path=_VERIFY_ENDPOINT,
    )

    assert response.status_code == 200
    assert response.json() == {"reset_token": "reset-token-opaco", "expires_in": 600}
    assert verify.calls == [("user@example.com", None, "123456", "127.0.0.1")]


async def test_verify_falha_retorna_400_generico_sem_pii() -> None:
    verify = _VerifyUseCase(error=PasswordRecoveryCodeError())
    app = _app(_RecordingUseCase(), verify=verify)

    response = await _post(
        app, {"email": "pii@example.com", "code": "000000"}, path=_VERIFY_ENDPOINT
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("password_recovery_code_invalid")
    assert "pii@example.com" not in response.text
    assert "000000" not in response.text


async def test_reset_valido_retorna_204_e_chama_caso_de_uso() -> None:
    reset = _ResetUseCase()
    app = _app(_RecordingUseCase(), reset=reset)

    response = await _post(
        app,
        {"reset_token": "token-opaco", "new_password": "NovaSenha@123"},
        path=_RESET_ENDPOINT,
    )

    assert response.status_code == 204
    assert response.content == b""
    assert reset.calls == [("token-opaco", "NovaSenha@123", "127.0.0.1")]


async def test_reset_senha_fraca_retorna_400() -> None:
    reset = _ResetUseCase(error=WeakPasswordError("Senha fraca."))
    app = _app(_RecordingUseCase(), reset=reset)

    response = await _post(
        app,
        {"reset_token": "token-opaco", "new_password": "curta"},
        path=_RESET_ENDPOINT,
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("weak_password")


async def test_reset_token_invalido_retorna_400_generico() -> None:
    reset = _ResetUseCase(error=PasswordResetTokenError())
    app = _app(_RecordingUseCase(), reset=reset)

    response = await _post(
        app,
        {"reset_token": "token-que-nao-existe", "new_password": "NovaSenha@123"},
        path=_RESET_ENDPOINT,
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("password_reset_token_invalid")
    assert "token-que-nao-existe" not in response.text


async def test_verify_e_reset_desabilitados_retornam_404() -> None:
    app = _app(_RecordingUseCase(), enabled=False)

    verify_response = await _post(
        app, {"email": "user@example.com", "code": "123456"}, path=_VERIFY_ENDPOINT
    )
    reset_response = await _post(
        app,
        {"reset_token": "token", "new_password": "NovaSenha@123"},
        path=_RESET_ENDPOINT,
    )

    assert verify_response.status_code == 404
    assert reset_response.status_code == 404


async def test_verify_xor_rejeita_ambos_e_nenhum() -> None:
    app = _app(_RecordingUseCase())

    both = await _post(
        app,
        {"email": "user@example.com", "phone": "+5511999991234", "code": "123456"},
        path=_VERIFY_ENDPOINT,
    )
    neither = await _post(app, {"code": "123456"}, path=_VERIFY_ENDPOINT)

    assert both.status_code == 422
    assert neither.status_code == 422


async def test_verify_phone_normaliza_e_aceita() -> None:
    verify = _VerifyUseCase()
    app = _app(_RecordingUseCase(), verify=verify)

    response = await _post(
        app,
        {"phone": "+55 (11) 99999-1234", "code": "123456"},
        path=_VERIFY_ENDPOINT,
    )

    assert response.status_code == 200
    assert verify.calls == [(None, "+5511999991234", "123456", "127.0.0.1")]
