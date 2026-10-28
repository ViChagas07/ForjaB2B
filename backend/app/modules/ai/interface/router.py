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
from app.core.errors import RateLimitExceededError
from app.core.request_context import client_ip
from app.interface.deps import get_locale, get_optional_auth
from app.modules.ai.application.chat import ChatResult, ChatService
from app.modules.ai.application.conversation_service import ConversationScope
from app.modules.ai.application.security.budget import estimate_tokens
from app.modules.ai.domain.security.injection import neutral_response
from app.modules.ai.domain.types import resolve_locale
from app.modules.ai.interface.schemas import ChatRequest, ChatResponse, card_to_out

router = APIRouter(prefix="/ai", tags=["ai"])

_BUDGET_RETRY_AFTER_SECONDS = 3600


def _chat_service(request: Request) -> ChatService:
    return cast(ChatService, request.app.state.ai_chat_service)


def _rate_limiter(request: Request) -> RateLimiter:
    return cast(RateLimiter, request.app.state.rate_limiter)


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
    locale: Annotated[str, Depends(get_locale)],
) -> ChatResponse:
    settings = request.app.state.settings
    locale_value = resolve_locale(locale)
    neutral = neutral_response(locale_value)

    # Kill switch: nenhuma chamada de LLM; resposta neutra e curta.
    if not settings.ai_agents_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=neutral)

    ip = client_ip(request.scope, settings.trusted_proxy_count)
    ip_decision = await limiter.check(
        rate_class=RateLimitClass.AI,
        identity=f"ip:{pseudonymous_key(settings.secret_key, ip)}",
    )
    if not ip_decision.allowed:
        raise RateLimitExceededError(
            retry_after_seconds=ip_decision.retry_after_seconds,
            limit=ip_decision.limit,
            remaining=ip_decision.remaining,
            reset_after_seconds=ip_decision.reset_after_seconds,
        )
    if payload.conversation_id is not None:
        conversation_identity = pseudonymous_key(settings.secret_key, str(payload.conversation_id))
        conversation_decision = await limiter.check(
            rate_class=RateLimitClass.AI,
            identity=f"conv:{conversation_identity}",
        )
        if not conversation_decision.allowed:
            raise RateLimitExceededError(
                retry_after_seconds=conversation_decision.retry_after_seconds,
                limit=conversation_decision.limit,
                remaining=conversation_decision.remaining,
                reset_after_seconds=conversation_decision.reset_after_seconds,
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
    result: ChatResult | None = await use_case.handle(
        conversation_id=payload.conversation_id,
        scope=scope,
        locale=locale,
        message=payload.message,
        auth=auth,
    )
    if result is None:
        # Inexistente OU fora do escopo: mesma resposta, sem vazar existencia.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=neutral)
    return ChatResponse(
        conversation_id=result.conversation_id,
        reply=result.reply,
        product_cards=[card_to_out(card) for card in result.product_cards],
    )
