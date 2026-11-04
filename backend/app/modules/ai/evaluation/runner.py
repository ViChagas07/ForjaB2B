"""Runner da avaliacao EDD do assistente (dataset versionado).

Avalia o passo "entender" (deterministico + LLM) e os filtros/follow-ups,
sem depender de prosa do modelo. O script real usa o mesmo runner com o
LM Studio; os testes usam um LLM mockado/scriptado.
"""

from __future__ import annotations

import importlib.resources
import json
import secrets
from dataclasses import dataclass
from typing import Any

from app.modules.ai.application.chat_session import (
    ChatSessionState,
    follow_up_decision,
)
from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    build_router_messages,
    deterministic_decision,
    fallback_decision,
    normalize_decision,
)
from app.modules.ai.application.lexicon import find_task
from app.modules.ai.application.ports import LLMPort
from app.modules.ai.domain.security.injection import scan_injection

_EVAL_FILE = "assistant_eval.v1.json"


@dataclass(frozen=True, kw_only=True)
class EvalCase:
    id: str
    locale: str
    message: str
    expected: dict[str, Any]
    session: dict[str, Any] | None = None

    @property
    def expected_intent(self) -> str:
        return str(self.expected.get("intent", "unknown"))


@dataclass(frozen=True, kw_only=True)
class EvalResult:
    id: str
    expected_intent: str
    passed: bool
    skipped: bool = False
    details: tuple[str, ...] = ()
    actual_intent: str = ""


def load_eval_cases() -> tuple[EvalCase, ...]:
    resource = importlib.resources.files("app.modules.ai.evaluation").joinpath(f"data/{_EVAL_FILE}")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return tuple(
        EvalCase(
            id=str(item["id"]),
            locale=str(item.get("locale", "pt-BR")),
            message=str(item["message"]),
            expected=dict(item.get("expected", {})),
            session=item.get("session"),
        )
        for item in payload["cases"]
    )


async def run_case(
    case: EvalCase, *, llm: LLMPort | None = None, deterministic_only: bool = False
) -> EvalResult:
    if case.expected.get("refusal"):
        return await _run_refusal_case(case, llm=llm, deterministic_only=deterministic_only)
    decision, skipped = await _decide_case(case, llm=llm, deterministic_only=deterministic_only)
    if decision is None:
        return EvalResult(
            id=case.id,
            expected_intent=case.expected_intent,
            passed=False,
            skipped=skipped,
            details=("requires_llm",) if skipped else ("no_decision",),
        )
    failures = _compare(case, decision)
    return EvalResult(
        id=case.id,
        expected_intent=case.expected_intent,
        passed=not failures,
        details=tuple(failures),
        actual_intent=decision.intent.value,
    )


async def _run_refusal_case(
    case: EvalCase, *, llm: LLMPort | None, deterministic_only: bool
) -> EvalResult:
    blocked = scan_injection(case.message).level.value == "BLOCK"
    decision = deterministic_decision(case.message, reply_language=case.locale)
    if decision is None and llm is not None and not deterministic_only:
        decision = await _ask_llm(case, llm)
    refused = blocked or (decision is not None and decision.intent == IntentName.OUT_OF_SCOPE)
    return EvalResult(
        id=case.id,
        expected_intent=case.expected_intent,
        passed=refused,
        actual_intent=decision.intent.value
        if decision is not None
        else ("out_of_scope" if blocked else "none"),
        details=() if refused else ("refusal_not_detected",),
    )


async def _decide_case(
    case: EvalCase, *, llm: LLMPort | None, deterministic_only: bool
) -> tuple[IntentDecision | None, bool]:
    if case.session is not None:
        session = ChatSessionState.from_json(json.dumps(case.session))
        if session is None:
            return None, False
        decision = follow_up_decision(session, case.message, reply_language=case.locale)
        return decision, False
    decision = deterministic_decision(case.message, reply_language=case.locale)
    if decision is None:
        if llm is None or deterministic_only:
            return None, True
        decision = await _ask_llm(case, llm)
    if decision is None:
        return None, False
    return normalize_decision(decision, message=case.message, reply_language=case.locale), False


async def run_dataset(
    cases: tuple[EvalCase, ...],
    *,
    llm: LLMPort | None = None,
    deterministic_only: bool = False,
) -> tuple[EvalResult, ...]:
    return tuple(
        [await run_case(case, llm=llm, deterministic_only=deterministic_only) for case in cases]
    )


def accuracy_by_intent(results: tuple[EvalResult, ...]) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = table.setdefault(result.expected_intent, {"passed": 0, "total": 0, "skipped": 0})
        bucket["total"] += 1
        if result.skipped:
            bucket["skipped"] += 1
        elif result.passed:
            bucket["passed"] += 1
    return table


async def _ask_llm(case: EvalCase, llm: LLMPort) -> IntentDecision | None:
    messages = build_router_messages(
        message=case.message,
        history=[],
        reply_language=case.locale,
        tag=secrets.token_hex(8),
    )
    try:
        decision = await llm.complete_structured(
            schema=IntentDecision, messages=messages, temperature=0.1
        )
    except Exception:  # noqa: BLE001 - LLM nunca derruba a avaliacao
        return fallback_decision(case.message, reply_language=case.locale)
    return normalize_decision(decision, message=case.message, reply_language=case.locale)


def _compare(case: EvalCase, decision: IntentDecision) -> list[str]:
    expected = case.expected
    failures: list[str] = []
    if "intent" in expected and decision.intent.value != expected["intent"]:
        failures.append(f"intent={decision.intent.value}")
    if "price_sort" in expected:
        actual = decision.price_sort.value if decision.price_sort else None
        if actual != expected["price_sort"]:
            failures.append(f"price_sort={actual}")
    failures.extend(_compare_fields(case, decision))
    failures.extend(_compare_details(case, decision))
    return failures


def _compare_fields(case: EvalCase, decision: IntentDecision) -> list[str]:
    failures: list[str] = []
    for field in (
        "price_min",
        "price_max",
        "task",
        "offset",
        "category",
        "quantity",
    ):
        if field in case.expected and getattr(decision, field) != _expected_value(
            field, case.expected[field]
        ):
            failures.append(f"{field}={getattr(decision, field)}")
    return failures


def _expected_value(field: str, value: object) -> object:
    """A tarefa agora e uma chave canonica; os casos antigos usam o termo PT."""
    if field == "task" and value is not None:
        return find_task(str(value))
    return value


def _compare_details(case: EvalCase, decision: IntentDecision) -> list[str]:
    failures: list[str] = []
    expected = case.expected
    query = expected.get("query_contains")
    if query and query.casefold() not in decision.query.casefold():
        failures.append(f"query={decision.query}")
    for key, value in expected.get("attributes", {}).items():
        if decision.attributes.get(key) != value:
            failures.append(f"attribute_{key}={decision.attributes.get(key)}")
    ref = expected.get("refs_contains")
    if ref and ref not in decision.product_refs:
        failures.append("refs_missing")
    if "refs_count" in expected and len(decision.product_refs) != expected["refs_count"]:
        failures.append(f"refs_count={len(decision.product_refs)}")
    return failures
