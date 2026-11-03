"""Avaliacao EDD: dataset, runner e caso deterministico obrigatorio."""

import json

import pytest

from app.modules.ai.application.intent_router import (
    IntentDecision,
    IntentName,
    PriceSort,
    deterministic_decision,
)
from app.modules.ai.evaluation.runner import (
    accuracy_by_intent,
    load_eval_cases,
    run_case,
    run_dataset,
)

MANDATORY = "Agente, quero as luvas mais baratas que você tem. Por favor, envie-me elas aqui."


def test_dataset_tem_40_casos_e_locales_esperados() -> None:
    cases = load_eval_cases()
    assert len(cases) >= 40
    assert {case.locale for case in cases} >= {"pt-BR", "en", "es"}
    mandatory = next(case for case in cases if case.id == "br_luvas_mais_baratas")
    assert mandatory.message == MANDATORY
    assert mandatory.expected["price_sort"] == "asc"


class ScriptedLLM:
    """LLM mockado com a decisao correta por mensagem (teste do runner)."""

    def __init__(self, decisions: dict[str, IntentDecision]) -> None:
        self.decisions = decisions
        self.calls: list[object] = []

    async def complete_structured(
        self,
        *,
        schema: object,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> object:
        self.calls.append(schema)
        text = "\n".join(message["content"] for message in messages)
        for message, decision in self.decisions.items():
            if message in text:
                return decision
        raise RuntimeError("sem roteiro")

    async def complete_text(
        self, *, messages: list[dict[str, str]], temperature: float | None = None
    ) -> str:
        raise AssertionError("nao usado")


def _decision_for(case: object) -> IntentDecision:
    expected = case.expected
    return IntentDecision(
        intent=IntentName(expected["intent"]),
        query=str(expected.get("query_contains") or case.message),
        category=expected.get("category"),
        price_sort=PriceSort(expected["price_sort"]) if expected.get("price_sort") else None,
        price_min=expected.get("price_min"),
        price_max=expected.get("price_max"),
        task=expected.get("task"),
        attributes=dict(expected.get("attributes", {})),
        product_refs=[expected["refs_contains"]] if expected.get("refs_contains") else [],
        offset=int(expected.get("offset", 0)),
        language=case.locale,
    )


class BrokenLLM:
    async def complete_structured(self, **_kwargs: object) -> object:
        raise RuntimeError("llm down")

    async def complete_text(self, **_kwargs: object) -> str:
        raise RuntimeError("llm down")


@pytest.mark.asyncio
async def test_runner_deterministico_nao_falha_nos_casos_cobertos() -> None:
    cases = load_eval_cases()
    results = await run_dataset(cases, deterministic_only=True)
    assert any(result.skipped for result in results)  # casos que exigem LLM
    for result in results:
        if not result.skipped:
            assert result.passed, (result.id, result.details)


@pytest.mark.asyncio
async def test_runner_com_llm_mockado_acerta_todos_os_casos() -> None:
    cases = load_eval_cases()
    decisions = {
        case.message: _decision_for(case)
        for case in cases
        if case.expected.get("intent") and case.session is None
    }
    results = await run_dataset(cases, llm=ScriptedLLM(decisions))
    failed = [result for result in results if not result.passed and not result.skipped]
    assert not failed, [(result.id, result.details) for result in failed]
    table = accuracy_by_intent(results)
    assert table["product_search"]["passed"] > 0
    assert table["product_search"]["passed"] == table["product_search"]["total"]


@pytest.mark.asyncio
async def test_caso_obrigatorio_passa_mesmo_com_llm_quebrado() -> None:
    case = next(case for case in load_eval_cases() if case.id == "br_luvas_mais_baratas")
    result = await run_case(case, llm=BrokenLLM())
    assert result.passed is True
    assert result.actual_intent == IntentName.PRODUCT_SEARCH.value


def test_atalho_do_caso_obrigatorio_e_deterministico() -> None:
    decision = deterministic_decision(MANDATORY, locale="pt-BR")
    assert decision is not None
    assert decision.intent == IntentName.PRODUCT_SEARCH
    assert decision.price_sort == PriceSort.ASC
    assert "luvas" in decision.query


@pytest.mark.asyncio
async def test_roteador_malformado_cai_em_product_search() -> None:
    case = next(case for case in load_eval_cases() if case.id == "br_ca")
    result = await run_case(case, llm=BrokenLLM())
    assert result.passed is False
    assert result.actual_intent == IntentName.PRODUCT_SEARCH.value
    assert "intent=product_search" in result.details


def test_dataset_json_e_valido() -> None:
    cases = load_eval_cases()
    assert all(case.id and case.message and case.locale for case in cases)
    ids = [case.id for case in cases]
    assert len(ids) == len(set(ids))
    # Nenhum campo de instrucao executavel no dataset.
    assert (
        "ignore previous"
        not in json.dumps([case.expected for case in cases], ensure_ascii=False).lower()
    )
