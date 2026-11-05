"""Endpoint do assistente de chat (FASE 5c) — POST /api/v1/ai/chat.

Kill switch `AI_AGENTS_ENABLED=false` => 503 com detalhe NEUTRO traduzido
(nenhum LLM e construido/instanciado no caminho). Rate limit da classe `AI`
por IP e, quando ha conversa, tambem por conversa (429 com Retry-After via
RateLimitExceededError). Orcamento diario de tokens estimados
(`AI_DAILY_TOKEN_BUDGET`) e consumido por turno. `company_id`/`user_id` vem
SEMPRE do JWT (get_optional_auth) — nunca do corpo.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.application.rate_limit import (
    RateLimitClass,
    RateLimiter,
    pseudonymous_key,
)
from app.application.security import AuthContext
from app.core.config import Settings
from app.core.errors import RateLimitExceededError
from app.core.logging import get_logger
from app.core.request_context import client_ip
from app.interface.deps import ChatLocaleInfo, get_chat_locale, get_optional_auth
from app.modules.ai.application.chat import ChatResult, ChatService
from app.modules.ai.application.conversation_service import ConversationScope
from app.modules.ai.application.security.budget import estimate_tokens
from app.modules.ai.domain.security.injection import neutral_response
from app.modules.ai.domain.types import resolve_locale
from app.modules.ai.interface.schemas import ChatRequest, ChatResponse, card_to_out

router = APIRouter(prefix="/ai", tags=["ai"])

_BUDGET_RETRY_AFTER_SECONDS = 3600
_logger = get_logger(__name__)


def _chat_service(request: Request) -> ChatService:
    return cast(ChatService, request.app.state.ai_chat_service)


def _rate_limiter(request: Request) -> RateLimiter:
    return cast(RateLimiter, request.app.state.rate_limiter)


async def _enforce_rate_limits(
    *,
    limiter: RateLimiter,
    settings: Settings,
    request: Request,
    payload: ChatRequest,
    auth: AuthContext | None,
) -> None:
    """Aplica os baldes AI (IP, conversa e usuario), sempre pseudonimos."""
    ip = client_ip(request.scope, settings.trusted_proxy_count)
    identities = [f"ip:{pseudonymous_key(settings.secret_key, ip)}"]
    if payload.conversation_id is not None:
        conversation = pseudonymous_key(settings.secret_key, str(payload.conversation_id))
        identities.append(f"conv:{conversation}")
    if auth is not None:
        user = pseudonymous_key(settings.secret_key, str(auth.user_id))
        identities.append(f"user:{user}")
    for identity in identities:
        decision = await limiter.check(rate_class=RateLimitClass.AI, identity=identity)
        if not decision.allowed:
            raise RateLimitExceededError(
                retry_after_seconds=decision.retry_after_seconds,
                limit=decision.limit,
                remaining=decision.remaining,
                reset_after_seconds=decision.reset_after_seconds,
            )


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        404: {"description": "Conversa inexistente ou fora do escopo"},
        429: {"description": "Limite de uso/orcamento excedido (Retry-After)"},
        503: {"description": "Agentes de IA desabilitados (kill switch)"},
    },
)
async def chat(
    payload: ChatRequest,
    request: Request,
    use_case: Annotated[ChatService, Depends(_chat_service)],
    limiter: Annotated[RateLimiter, Depends(_rate_limiter)],
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
    chat_locale: Annotated[ChatLocaleInfo, Depends(get_chat_locale)],
) -> ChatResponse:
    settings = request.app.state.settings
    locale_value = resolve_locale(chat_locale.reply_language)
    neutral = neutral_response(locale_value)

    # Kill switch: nenhuma chamada de LLM; resposta neutra e curta.
    if not settings.ai_agents_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=neutral)

    await _enforce_rate_limits(
        limiter=limiter,
        settings=settings,
        request=request,
        payload=payload,
        auth=auth,
    )

    # Orcamento diario: roteador + resposta podem consumir ate 2x max_tokens.
    estimated = estimate_tokens(len(payload.message)) + settings.llm_max_tokens * 2
    budget = request.app.state.ai_token_budget
    if not budget.try_consume(estimated_tokens=estimated):
        raise RateLimitExceededError(
            retry_after_seconds=_BUDGET_RETRY_AFTER_SECONDS,
            limit=settings.ai_daily_token_budget,
            remaining=0,
            reset_after_seconds=_BUDGET_RETRY_AFTER_SECONDS,
        )

    scope = (
        ConversationScope(company_id=auth.company_id, user_id=auth.user_id)
        if auth is not None
        else ConversationScope(company_id=None, user_id=None)
    )
    try:
        result: ChatResult | None = await use_case.handle(
            conversation_id=payload.conversation_id,
            scope=scope,
            site_locale=chat_locale.reply_language,
            content_locale=chat_locale.content_locale,
            message=payload.message,
            auth=auth,
        )
    except Exception as exc:
        _logger.exception("chat_request_failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=neutral
        ) from exc
    if result is None:
        # Inexistente OU fora do escopo: mesma resposta, sem vazar existencia.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=neutral)
    return ChatResponse(
        conversation_id=result.conversation_id,
        reply=result.reply,
        product_cards=[card_to_out(card) for card in result.product_cards],
        language=result.language,
        degraded=result.degraded,
        language_mismatch=result.language_mismatch,
        detected_language=result.detected_language,
    )
