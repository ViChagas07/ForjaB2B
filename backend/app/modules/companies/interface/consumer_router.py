"""Endpoint publico de cadastro de cliente consumidor (conta CPF).

Mesmo limite de taxa do onboarding B2B, chaveado pelo e-mail pseudonimizado:
o objetivo e conter criacao automatizada de contas sem revelar o e-mail.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from app.application.rate_limit import RateLimitClass, RateLimiter, pseudonymous_key
from app.core.errors import RateLimitExceededError
from app.modules.companies.application.consumer import (
    RegisterConsumer,
    RegisterConsumerCommand,
)
from app.modules.companies.interface.schemas import (
    RegisterConsumerRequest,
    RegisterConsumerResponse,
)

router = APIRouter(prefix="/consumers", tags=["consumers"])


def _register_usecase(request: Request) -> RegisterConsumer:
    return cast(RegisterConsumer, request.app.state.companies_register_consumer)


def _rate_limiter(request: Request) -> RateLimiter:
    return cast(RateLimiter, request.app.state.rate_limiter)


@router.post("", response_model=RegisterConsumerResponse, status_code=status.HTTP_201_CREATED)
async def register_consumer(
    payload: RegisterConsumerRequest,
    request: Request,
    use_case: Annotated[RegisterConsumer, Depends(_register_usecase)],
    limiter: Annotated[RateLimiter, Depends(_rate_limiter)],
) -> RegisterConsumerResponse:
    settings = request.app.state.settings
    account_identity = pseudonymous_key(settings.secret_key, payload.email)
    decision = await limiter.check(
        rate_class=RateLimitClass.REGISTRATION,
        identity=f"account:{account_identity}",
    )
    if not decision.allowed:
        raise RateLimitExceededError(
            retry_after_seconds=decision.retry_after_seconds,
            limit=decision.limit,
            remaining=decision.remaining,
            reset_after_seconds=decision.reset_after_seconds,
        )

    result = await use_case.register(
        RegisterConsumerCommand(
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
            cpf=payload.cpf,
            birth_date=payload.birth_date,
            postal_code=payload.postal_code,
            gender=payload.gender.value,
            consent=payload.consent,
        )
    )
    return RegisterConsumerResponse(company_id=result.company_id, user_id=result.user_id)
