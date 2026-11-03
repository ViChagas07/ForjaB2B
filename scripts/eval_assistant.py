#!/usr/bin/env python
"""Avaliacao EDD do assistente Forja (roteador + filtros/follow-ups).

Uso (com o backend/.venv):
    backend/.venv/Scripts/python.exe scripts/eval_assistant.py
    backend/.venv/Scripts/python.exe scripts/eval_assistant.py --deterministic-only
    backend/.venv/Scripts/python.exe scripts/eval_assistant.py --case br_luvas_mais_baratas

O script usa o MESMO dataset/runner dos testes. Sem LM Studio ele ainda
avalia os casos deterministicos e marca os demais como skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
from app.modules.ai.evaluation.runner import (
    accuracy_by_intent,
    load_eval_cases,
    run_dataset,
)
from app.modules.ai.infrastructure.llm_openai import LangChainOpenAILLM


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Eval EDD do assistente Forja")
    parser.add_argument(
        "--base-url",
        default=os.getenv("LLM_BASE_URL", "http://localhost:1235/v1"),
        help="Endpoint OpenAI-like do LM Studio",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "qwen/qwen3.5-9b"),
        help="ID exato do modelo carregado",
    )
    parser.add_argument("--api-key", default=os.getenv("LLM_API_KEY", "lm-studio"))
    parser.add_argument(
        "--timeout", type=float, default=float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    )
    parser.add_argument("--case", default=None, help="Filtra um id de caso")
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Nao chama o LLM; casos que exigem modelo aparecem como skipped",
    )
    parser.add_argument("--json", action="store_true", help="Saida JSON")
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    cases = load_eval_cases()
    if args.case:
        cases = tuple(case for case in cases if case.id == args.case)
        if not cases:
            print(f"caso nao encontrado: {args.case}", file=sys.stderr)
            return 2

    llm = None
    llm_available = False
    if not args.deterministic_only:
        llm_available = await _llm_available(args.base_url)
        if llm_available:
            llm = LangChainOpenAILLM(
                base_url=args.base_url.rstrip("/"),
                api_key=args.api_key,
                model=args.model,
                timeout_seconds=args.timeout,
                max_tokens=512,
                temperature=0.1,
                reasoning_effort="none",
            )
        else:
            print(
                f"[aviso] LM Studio indisponivel em {args.base_url}; "
                "avaliando apenas casos deterministicos (os demais ficam skipped).",
                file=sys.stderr,
            )

    results = await run_dataset(
        cases,
        llm=llm,
        deterministic_only=args.deterministic_only or not llm_available,
    )
    table = accuracy_by_intent(results)
    overall_total = sum(item["total"] for item in table.values())
    overall_skipped = sum(item["skipped"] for item in table.values())
    overall_passed = sum(item["passed"] for item in table.values())
    evaluated = overall_total - overall_skipped

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "llm_available": llm_available,
                    "overall": {
                        "passed": overall_passed,
                        "evaluated": evaluated,
                        "skipped": overall_skipped,
                    },
                    "by_intent": table,
                    "cases": [
                        {
                            "id": result.id,
                            "passed": result.passed,
                            "skipped": result.skipped,
                            "expected_intent": result.expected_intent,
                            "actual_intent": result.actual_intent,
                            "details": list(result.details),
                        }
                        for result in results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"LLM: {'LM Studio real' if llm_available else 'deterministico/sem LLM'}")
        print(f"{'intent':<24} {'acertos':>8} {'avaliados':>10} {'skipped':>8}")
        for intent, item in sorted(table.items()):
            evaluated_intent = item["total"] - item["skipped"]
            print(
                f"{intent:<24} {item['passed']:>8} {evaluated_intent:>10} "
                f"{item['skipped']:>8}"
            )
        failures = [
            result for result in results if not result.passed and not result.skipped
        ]
        for failure in failures:
            print(
                f"FAIL {failure.id} expected={failure.expected_intent} "
                f"actual={failure.actual_intent} details={','.join(failure.details)}"
            )
        accuracy = (overall_passed / evaluated * 100) if evaluated else 0.0
        print(
            f"\nAcerto geral: {overall_passed}/{evaluated} "
            f"({accuracy:.1f}%) | skipped: {overall_skipped}"
        )

    return 0 if all(result.passed or result.skipped for result in results) else 1


async def _llm_available(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base_url.rstrip('/')}/models")
            return response.status_code == 200
    except Exception:  # noqa: BLE001 - eval deve rodar deterministico sem LM Studio
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(main()))
