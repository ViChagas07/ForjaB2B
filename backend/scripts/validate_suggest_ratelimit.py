"""Simulacao de uso real do dropdown contra /api/v1/search/suggest.

Dispara uma sequencia de chamadas em rajada (debounce humano simulado) para
dois IPs distintos via ``X-Forwarded-For`` e, no final, consulta
``/search/products`` com o mesmo IP do burst para verificar se o balde
SEARCH e compartilhado entre suggest e products. Somente leitura; nenhum
dado e gravado. Uso:

    python scripts/validate_suggest_ratelimit.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

import httpx


def burst(
    client: httpx.Client,
    *,
    path: str,
    ip: str,
    calls: int,
    interval_seconds: float,
) -> Counter[int]:
    """Roda ``calls`` chamadas espacadas; devolve contagem por status HTTP."""
    statuses: Counter[int] = Counter()
    for index in range(calls):
        response = client.get(
            path,
            params={"q": f"cap{index % 3}"},
            headers={"X-Forwarded-For": ip},
        )
        statuses[response.status_code] += 1
        if response.status_code == 429:
            print(f"    429 recebido (Retry-After={response.headers.get('retry-after')})")
        time.sleep(interval_seconds)
    return statuses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--calls", type=int, default=12, help="chamadas por IP")
    parser.add_argument("--interval", type=float, default=0.5, help="segundos entre chamadas")
    parser.add_argument(
        "--stress-calls",
        type=int,
        default=40,
        help="cenario de pressao adicional (IP dedicado) para achar o limiar de 429",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=15.0) as client:
        duration = args.calls * args.interval
        print(f"=== uso real: {args.calls} chamadas em ~{duration:.0f}s por IP ===")
        for ip in ("203.0.113.10", "203.0.113.11"):
            statuses = burst(
                client,
                path="/api/v1/search/suggest",
                ip=ip,
                calls=args.calls,
                interval_seconds=args.interval,
            )
            print(f"IP {ip} /suggest: {args.calls} chamadas -> {dict(statuses)}")

        print("=== compartilhamento de balde: /search/products com o mesmo IP do burst ===")
        statuses = burst(
            client,
            path="/api/v1/search/products",
            ip="203.0.113.10",
            calls=3,
            interval_seconds=0.2,
        )
        print(f"IP 203.0.113.10 /products apos o burst -> {dict(statuses)}")

        if args.stress_calls > 0:
            print(f"=== pressao: {args.stress_calls} chamadas seguidas (IP dedicado) ===")
            statuses = burst(
                client,
                path="/api/v1/search/suggest",
                ip="203.0.113.99",
                calls=args.stress_calls,
                interval_seconds=0.1,
            )
            print(f"IP 203.0.113.99 /suggest: {args.stress_calls} chamadas -> {dict(statuses)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
