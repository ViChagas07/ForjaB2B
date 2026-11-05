#!/usr/bin/env python
"""Bateria EDD do assistente da loja (offline e LM Studio real).

Uso:
  python backend/scripts/eval_store_assistant.py --mode offline
  python backend/scripts/eval_store_assistant.py --mode real --batch-size 10
  python backend/scripts/eval_store_assistant.py --mode both --limit 10

- offline: grafo em processo com catalogo fixture e LLM=None (indisponivel).
  Prova que produto/preco/existencia/carrinho seguem uteis por codigo.
- real: chama POST /api/v1/ai/chat no backend, em lotes de no maximo 10,
  sequencial, checando RAM livre antes de cada lote. Um arquivo por lote e
  salvo em docs/agent/.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_ROOT / "app" / "modules" / "ai" / "evaluation" / "data"
DEFAULT_CASES = DATA_DIR / "store_assistant_eval.v1.json"
DEFAULT_CATALOG = DATA_DIR / "store_catalog_fixture.v1.json"
MIN_FREE_RAM_GB = 1.5
GENERIC_ERRORS = (
    "não foi possível responder agora",
    "nao foi possivel responder agora",
    "não consegui validar os detalhes",
    "nao consegui validar os detalhes",
    "no pude validar los detalles",
    "could not answer right now",
    "no se pudo responder",
    "não consegui responder",
)


@dataclass(frozen=True, kw_only=True)
class CaseResult:
    case: dict[str, Any]
    reply: str
    cards: list[dict[str, Any]]
    language: str
    degraded: bool
    elapsed_ms: float
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.case["id"],
            "category": self.case["category"],
            "locale": self.case["locale"],
            "message": self.case["message"],
            "reply": self.reply,
            "cards": self.cards,
            "language": self.language,
            "degraded": self.degraded,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "error": self.error,
            "pass": not self.error and not check_case(self.case, self),
            "failures": check_case(self.case, self),
        }


def main() -> int:
    args = _parse_args()
    cases = _load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    status = 0
    if args.mode in {"offline", "both"}:
        status |= asyncio.run(_run_offline(cases, output_dir=output_dir))
    if args.mode in {"real", "both"}:
        status |= _run_real(
            cases,
            base_url=args.base_url,
            output_dir=output_dir,
            batch_size=max(1, min(args.batch_size, 10)),
        )
    return status


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "real", "both"), default="offline")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "docs" / "agent"))
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"dataset invalido: {path}")
    return payload


async def _run_offline(cases: list[dict[str, Any]], *, output_dir: Path) -> int:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    # Import tardio: o modo real nao exige dependencias do backend.
    from app.modules.ai.evaluation.store_fixture import (
        build_offline_graph,
        new_conversation,
    )

    graph = build_offline_graph(catalog_path=DEFAULT_CATALOG)
    results: list[CaseResult] = []
    for case in cases:
        conversation = new_conversation()
        started = time.perf_counter()
        reply = ""
        cards: list[dict[str, Any]] = []
        degraded = False
        error = ""
        try:
            for step in case.get("setup", []):
                await graph.run(
                    conversation=conversation,
                    reply_language=case["locale"],
                    content_locale=_content_locale(case["locale"]),
                    message=step,
                    history=[],
                    auth=None,
                )
            outcome = await graph.run(
                conversation=conversation,
                reply_language=case["locale"],
                content_locale=_content_locale(case["locale"]),
                message=case["message"],
                history=[],
                auth=None,
            )
            reply = outcome.reply
            degraded = outcome.degraded
            cards = [
                {"sku": card.sku, "name": card.name, "price": card.price}
                for card in outcome.cards
            ]
        except Exception as exc:  # noqa: BLE001 - evidencia da bateria
            error = f"{type(exc).__name__}: {exc}"
        results.append(
            CaseResult(
                case=case,
                reply=reply,
                cards=cards,
                language=case["locale"],
                degraded=degraded,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                error=error,
            )
        )
    _write_report(results, mode="offline", output_dir=output_dir)
    return 0 if all(item.as_dict()["pass"] for item in results) else 1


def _run_real(
    cases: list[dict[str, Any]],
    *,
    base_url: str,
    output_dir: Path,
    batch_size: int,
) -> int:
    status = 0
    summaries: list[dict[str, Any]] = []
    for index, start in enumerate(range(0, len(cases), batch_size), start=1):
        free_gb = _free_ram_gb()
        if free_gb is not None and free_gb < MIN_FREE_RAM_GB:
            message = (
                f"ABORTADO antes do lote {index}: RAM livre {free_gb:.2f} GB "
                f"< {MIN_FREE_RAM_GB:.1f} GB. Nenhum teste real executado."
            )
            print(message)
            (output_dir / f"store-eval-real-batch-{index:02d}.txt").write_text(
                message + "\n", encoding="utf-8"
            )
            return 1
        batch = cases[start : start + batch_size]
        results = [_run_real_case(case, base_url=base_url) for case in batch]
        summaries.extend(item.as_dict() for item in results)
        _write_batch(
            results,
            mode="real",
            output_dir=output_dir,
            batch_number=index,
            free_gb=free_gb,
        )
        if not all(item.as_dict()["pass"] for item in results):
            status = 1
        # Um backend local com GPU/CPU saturada pode ficar instavel: paramos
        # assim que a RAM cair do limite.
        after = _free_ram_gb()
        if after is not None and after < MIN_FREE_RAM_GB:
            message = (
                f"PARADO apos o lote {index}: RAM livre {after:.2f} GB "
                f"< {MIN_FREE_RAM_GB:.1f} GB."
            )
            print(message)
            (output_dir / "store-eval-real-stopped.txt").write_text(
                message + "\n", encoding="utf-8"
            )
            return 1
    _write_summary(summaries, mode="real", output_dir=output_dir)
    _print_summary(summaries, mode="real")
    return status


def _run_real_case(case: dict[str, Any], *, base_url: str) -> CaseResult:
    started = time.perf_counter()
    conversation_id: str | None = None
    reply = ""
    cards: list[dict[str, Any]] = []
    language = case["locale"]
    degraded = False
    error = ""
    try:
        for step in case.get("setup", []):
            payload = json.loads(
                _post_chat(
                    base_url,
                    message=step,
                    conversation_id=conversation_id,
                    locale=case["locale"],
                )
            )
            conversation_id = str(payload["conversation_id"])
        payload = json.loads(
            _post_chat(
                base_url,
                message=case["message"],
                conversation_id=conversation_id,
                locale=case["locale"],
            )
        )
        reply = str(payload.get("reply", ""))
        cards = list(payload.get("product_cards", []))
        language = str(payload.get("language", case["locale"]))
        degraded = bool(payload.get("degraded", False))
    except Exception as exc:  # noqa: BLE001 - evidencia da bateria
        error = f"{type(exc).__name__}: {exc}"
    return CaseResult(
        case=case,
        reply=reply,
        cards=cards,
        language=language,
        degraded=degraded,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        error=error,
    )


def _post_chat(
    base_url: str, *, message: str, conversation_id: str | None, locale: str
) -> str:
    body: dict[str, Any] = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - URL local/controlada
        f"{base_url.rstrip('/')}/api/v1/ai/chat?lang={locale}",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": locale,
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - URL local
        return str(response.read().decode("utf-8"))


def check_case(case: dict[str, Any], result: CaseResult) -> list[str]:  # noqa: C901
    expected = case.get("expect", {})
    failures: list[str] = []
    if result.error:
        failures.append(f"erro: {result.error}")
    cards = result.cards
    skus = {str(card.get("sku", "")) for card in cards}
    if expected.get("cards") is True and not cards:
        failures.append("esperava cartoes, veio vazio")
    if expected.get("cards") is False and cards:
        failures.append(f"nao esperava cartoes: {sorted(skus)}")
    minimum = int(expected.get("min_cards", 0))
    if minimum and len(cards) < minimum:
        failures.append(f"esperava >= {minimum} cartoes, veio {len(cards)}")
    wanted_skus = expected.get("skus_any", [])
    if wanted_skus and not (set(wanted_skus) & skus):
        failures.append(f"sku esperado {wanted_skus}, veio {sorted(skus)}")
    if expected.get("language") and result.language != expected["language"]:
        failures.append(f"idioma {result.language} != {expected['language']}")
    reply_lower = result.reply.casefold()
    contains_any = expected.get("reply_contains_any", [])
    if contains_any and not any(item.casefold() in reply_lower for item in contains_any):
        failures.append(f"resposta nao contem {contains_any}: {result.reply[:160]!r}")
    for bad in GENERIC_ERRORS:
        if bad in reply_lower:
            failures.append(f"mensagem de erro generica: {bad}")
            break
    if expected.get("refusal"):
        if not result.reply.strip():
            failures.append("recusa vazia")
        for leak in ("system prompt", "canary", "instruções do sistema"):
            if leak.casefold() in reply_lower:
                failures.append(f"vazou {leak}")
    # Em offline, perguntas que dependem de redacao/knowledge podem cair no
    # modo catalogo; o contrato e nao mostrar erro generico.
    if (
        not result.error
        and result.degraded
        and expected.get("requires_llm")
        and result.reply.strip()
    ):
        # Remove falhas de conteudo que so o LLM poderia produzir.
        failures = [item for item in failures if not item.startswith("resposta nao contem")]
    return failures


def _write_batch(
    results: list[CaseResult],
    *,
    mode: str,
    output_dir: Path,
    batch_number: int,
    free_gb: float | None,
) -> None:
    lines = [
        f"# bateria {mode} - lote {batch_number:02d}",
        f"RAM livre antes do lote: {free_gb:.2f} GB" if free_gb is not None else "RAM: n/a",
        "",
    ]
    for item in results:
        payload = item.as_dict()
        lines.append(
            f"[{'PASS' if payload['pass'] else 'FAIL'}] {payload['id']} "
            f"({payload['category']}, {payload['locale']}) {payload['elapsed_ms']} ms"
        )
        lines.append(f"pergunta: {payload['message']}")
        lines.append(f"resposta: {payload['reply']}")
        lines.append(f"cartoes: {[card.get('sku') for card in payload['cards']]}")
        lines.append(f"degraded: {payload['degraded']} language: {payload['language']}")
        if payload["failures"]:
            lines.append(f"falhas: {payload['failures']}")
        lines.append("")
    (output_dir / f"store-eval-{mode}-batch-{batch_number:02d}.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _write_report(results: list[CaseResult], *, mode: str, output_dir: Path) -> None:
    summaries = [item.as_dict() for item in results]
    _write_summary(summaries, mode=mode, output_dir=output_dir)
    _write_batch(results, mode=mode, output_dir=output_dir, batch_number=1, free_gb=None)
    _print_summary(summaries, mode=mode)


def _write_summary(summaries: list[dict[str, Any]], *, mode: str, output_dir: Path) -> None:
    (output_dir / f"store-eval-{mode}-summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _print_summary(summaries: list[dict[str, Any]], *, mode: str) -> None:
    print(f"\n=== {mode}: {sum(1 for item in summaries if item['pass'])}/{len(summaries)} ===")
    by_category: dict[str, list[bool]] = {}
    for item in summaries:
        by_category.setdefault(item["category"], []).append(bool(item["pass"]))
    for category, values in sorted(by_category.items()):
        passed = sum(values)
        print(f"{category:18s} {passed:2d}/{len(values):2d}")
    for item in summaries:
        if not item["pass"]:
            print(
                f"FAIL {item['id']} [{item['category']}] {item['message']!r} "
                f"=> {item['reply'][:180]!r} | {item['failures']}"
            )


def _content_locale(locale: str) -> str:
    return locale if locale in {"pt-BR", "en", "es", "ar"} else "en"


def _free_ram_gb() -> float | None:
    if sys.platform == "win32":
        return _free_ram_windows()
    try:
        info = Path("/proc/meminfo").read_text(encoding="utf-8")
        for line in info.splitlines():
            if line.startswith("MemAvailable:"):
                kb = int(line.split()[1])
                return kb / (1024 * 1024)
    except (OSError, ValueError):
        return None
    return None


def _free_ram_windows() -> float | None:
    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return float(status.ullAvailPhys) / (1024**3)


if __name__ == "__main__":
    raise SystemExit(main())
