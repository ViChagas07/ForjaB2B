# ruff: noqa: RUF001 - frases intencionais nos 11 idiomas
"""Smoke test REAL do idioma dinamico do chat contra LM Studio + API local.

Pre-requisitos:
- backend rodando (ex.: ``uvicorn app.main:app``) com ``AI_AGENTS_ENABLED=true``
  e o catalogo demo semeado (o seed tem luvas e capacetes);
- LM Studio ouvindo em ``http://localhost:1235/v1`` (ajuste ``--llm-url``).

O script:
1. checa o endpoint do LM Studio e a API;
2. inicia a conversa em pt-BR (site pt-BR) pedindo as luvas mais baratas;
3. troca para os outros 10 idiomas na MESMA conversa, pedindo as luvas mais
   baratas e um follow-up curto ("e a mais cara?");
4. reporta idioma, cards, ordem de preco e latencia de cada turno.

Uso:
    python scripts/ai_language_smoke.py
    python scripts/ai_language_smoke.py --base-url http://localhost:8000 \
        --llm-url http://localhost:1235/v1
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

PHRASES: dict[str, tuple[str, str]] = {
    "pt-BR": ("quero as luvas mais baratas", "e a mais cara?"),
    "en": ("show me the cheapest gloves", "and the most expensive?"),
    "es": ("muéstrame los guantes más baratos", "¿y la más cara?"),
    "de": ("zeig mir die günstigsten Handschuhe", "und die teuerste?"),
    "fr": ("montre-moi les gants les moins chers", "et la plus chère ?"),
    "it": ("mostrami i guanti più economici", "e la più cara?"),
    "ru": ("покажи самые дешёвые перчатки", "а самая дорогая?"),
    "ar": ("أرني أرخص القفازات", "والأغلى؟"),
    "ja": ("一番安い手袋を見せて", "一番高いのは?"),
    "ko": ("가장 저렴한 장갑을 보여줘", "가장 비싼 것은?"),
    "zh-CN": ("给我看最便宜的手套", "最贵的呢?"),
}


@dataclass(frozen=True, kw_only=True)
class TurnReport:
    language: str
    phase: str
    status: int
    cards: int
    prices: list[str]
    ordered: bool
    latency_ms: float
    reply: str


def _get_json(url: str, *, timeout: float) -> tuple[int, object | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"ERRO ao acessar {url}: {exc}")
        return 0, None


def _post_json(
    url: str, payload: dict[str, object], *, timeout: float
) -> tuple[int, object | None, float]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
            return response.status, data, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"HTTP {exc.code} em {url}: {detail}")
        return exc.code, None, (time.perf_counter() - started) * 1000
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"ERRO ao acessar {url}: {exc}")
        return 0, None, (time.perf_counter() - started) * 1000


def _prices(cards: object) -> list[str]:
    if not isinstance(cards, list):
        return []
    values: list[str] = []
    for card in cards:
        if isinstance(card, dict) and card.get("price") is not None:
            values.append(str(card["price"]))
    return values


def _ordered(prices: list[str], *, phase: str) -> bool:
    parsed: list[Decimal] = []
    for value in prices:
        try:
            parsed.append(Decimal(str(value)))
        except InvalidOperation:
            return False
    expected = sorted(parsed, reverse=phase == "follow")
    return parsed == expected


def _report(turn: TurnReport) -> None:
    intent = "product_search" if turn.cards else "unknown"
    print(
        f"{turn.language:6s} {turn.phase:8s} intent={intent:14s} "
        f"status={turn.status:3d} cards={turn.cards} ordem_ok={turn.ordered} "
        f"latencia={turn.latency_ms:7.1f} ms reply={turn.reply[:70]!r}"
    )


def main() -> int:  # noqa: C901 - CLI de smoke test
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--llm-url", default="http://localhost:1235/v1")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--conversation-id", default=None)
    parser.add_argument("--languages", default=None, help="ex.: pt-BR,en,es (default: todos)")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    llm_url = args.llm_url.rstrip("/")
    llm_status, llm_data = _get_json(f"{llm_url}/models", timeout=10)
    if llm_status != 200:
        print(
            f"LM Studio indisponivel em {llm_url}/models (status={llm_status}). "
            "Inicie o LM Studio, carregue o Qwen e rode de novo."
        )
        return 2
    model = args.model
    if model is None and isinstance(llm_data, dict):
        items = llm_data.get("data")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            model = str(items[0].get("id") or "") or None
    if model is None:
        print("Nao consegui descobrir o model id em /v1/models; use --model.")
        return 2
    probe_status, probe_data, _ = _post_json(
        f"{llm_url}/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": "Responda apenas OK."}],
            "temperature": 0,
            "max_tokens": 16,
        },
        timeout=min(args.timeout, 120),
    )
    if probe_status != 200:
        print(f"LM Studio nao carregou o modelo {model!r}: {probe_data}")
        return 2

    api_status, api_data = _get_json(f"{args.base_url.rstrip('/')}/health/ready", timeout=10)
    if api_status != 200:
        print(
            f"API nao esta pronta em {args.base_url}/health/ready (status={api_status}): {api_data}"
        )
        print(
            "Suba o backend com AI_AGENTS_ENABLED=true, LLM_BASE_URL correto e o catalogo semeado."
        )
        return 3

    chat_url = f"{args.base_url.rstrip('/')}/api/v1/ai/chat"
    conversation_id = args.conversation_id
    if args.languages:
        requested = [item.strip() for item in args.languages.split(",") if item.strip()]
        selected = [(lang, PHRASES[lang]) for lang in requested if lang in PHRASES]
        if not selected:
            print(f"Nenhum idioma valido em --languages: {args.languages}")
            return 4
    else:
        selected = list(PHRASES.items())
    reports: list[TurnReport] = []
    latencies: list[float] = []

    for index, (language, (phrase, follow_up)) in enumerate(selected):
        payload: dict[str, object] = {"message": phrase}
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        status, data, latency = _post_json(chat_url, payload, timeout=args.timeout)
        if isinstance(data, dict):
            if index == 0:
                conversation_id = str(data.get("conversation_id") or "") or None
                if conversation_id:
                    print(f"CONVERSATION {conversation_id}")
            prices = _prices(data.get("product_cards"))
            report = TurnReport(
                language=language,
                phase="busca",
                status=status,
                cards=len(prices),
                prices=prices,
                ordered=_ordered(prices, phase="busca"),
                latency_ms=latency,
                reply=str(data.get("reply") or ""),
            )
        else:
            report = TurnReport(
                language=language,
                phase="busca",
                status=status,
                cards=0,
                prices=[],
                ordered=False,
                latency_ms=latency,
                reply="",
            )
        reports.append(report)
        latencies.append(latency)
        _report(report)

        follow_payload: dict[str, object] = {"message": follow_up}
        if conversation_id is not None:
            follow_payload["conversation_id"] = conversation_id
        follow_status, follow_data, follow_latency = _post_json(
            chat_url, follow_payload, timeout=args.timeout
        )
        if isinstance(follow_data, dict):
            follow_prices = _prices(follow_data.get("product_cards"))
            follow_report = TurnReport(
                language=language,
                phase="follow",
                status=follow_status,
                cards=len(follow_prices),
                prices=follow_prices,
                ordered=_ordered(follow_prices, phase="follow"),
                latency_ms=follow_latency,
                reply=str(follow_data.get("reply") or ""),
            )
        else:
            follow_report = TurnReport(
                language=language,
                phase="follow",
                status=follow_status,
                cards=0,
                prices=[],
                ordered=False,
                latency_ms=follow_latency,
                reply="",
            )
        reports.append(follow_report)
        latencies.append(follow_latency)
        _report(follow_report)
        # Limite de carga: uma pausa curta entre idiomas evita rajada na GPU.
        time.sleep(6)

    failed = [
        report
        for report in reports
        if report.status != 200 or report.cards == 0 or not report.ordered
    ]
    if latencies:
        print(
            f"\nlatencia mediana={statistics.median(latencies):.1f} ms "
            f"p95={sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]:.1f} ms "
            f"turnos={len(latencies)}"
        )
    if failed:
        print(f"FALHAS: {len(failed)} turno(s) sem cards/ordem/HTTP 200")
        return 1
    print("OK: todos os idiomas devolveram luvas na ordem esperada por fase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
