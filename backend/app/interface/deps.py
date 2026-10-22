"""Dependencias FastAPI compartilhadas (composicao de raiz + autenticacao).

A raiz de composicao (app.main) guarda em ``app.state`` os objetos de
infraestrutura singulares (settings, engine, session factory, UoW factory,
cliente Redis). Estas dependencias leem esses objetos e, no caso da
autenticacao, extraem e validam o bearer token, devolvendo ``AuthContext``.

Nenhuma dependencia aqui confia em company_id/role vindos do cliente: a
identidade vem exclusivamente do token assinado pelo servidor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

import redis.asyncio as redis
from fastapi import Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.security import AuthContext, InvalidTokenError, TokenService
from app.core.config import Settings
from app.domain.i18n import negotiate_locale

_BEARER_PREFIX = "Bearer "


@dataclass(frozen=True, kw_only=True)
class LocaleInfo:
    """Informacoes de idioma resolvidas para a requisicao."""

    ui_locale: str
    content_locale: str
    content_fallback: bool


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_locale_info(request: Request, lang: str | None = Query(default=None)) -> LocaleInfo:
    """Resolve idiomas: UI (para frontend) e Conteudo (para backend).

    ``?lang=`` > ``Accept-Language`` > default.
    UI locale negocia contra UI_LOCALES (11 idiomas).
    Content locale: se UI locale em CONTENT_LOCALES (4), usa-o; senao usa ``en``.
    Retorna tambem flag de fallback de idioma.
    """
    settings: Settings = request.app.state.settings
    ui_locale, content_locale, content_fallback = negotiate_locale(
        accept_language=request.headers.get("accept-language"),
        lang_param=lang,
        ui_locales=settings.ui_locale_list,
        content_locales=settings.supported_locale_list,
        default=settings.default_locale,
    )
    return LocaleInfo(
        ui_locale=ui_locale,
        content_locale=content_locale,
        content_fallback=content_fallback,
    )


# Compatibilidade: dependencia que devolve apenas o content_locale (string)
def get_locale(request: Request, lang: str | None = Query(default=None)) -> str:
    """Idioma do conteudo (compatibilidade): ``?lang=`` > ``Accept-Language`` > default."""
    return get_locale_info(request, lang).content_locale


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)


def get_uow_factory(request: Request) -> UnitOfWorkFactory:
    return cast(UnitOfWorkFactory, request.app.state.uow_factory)


def get_redis_client(request: Request) -> redis.Redis[str]:
    return cast(redis.Redis[str], request.app.state.redis_client)


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenService:
    return TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if not authorization.startswith(_BEARER_PREFIX):
        return None
    token = authorization[len(_BEARER_PREFIX) :].strip()
    return token or None


async def get_current_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    token = _extract_bearer_token(authorization)
    if token is None:
        raise InvalidTokenError()
    settings: Settings = request.app.state.settings
    token_service = TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )
    return token_service.decode_access_token(token)


async def get_optional_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext | None:
    token = _extract_bearer_token(authorization)
    if token is None:
        return None
    settings: Settings = request.app.state.settings
    token_service = TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )
    return token_service.decode_access_token(token)
