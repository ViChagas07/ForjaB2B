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
import asyncio
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


async def parallel_burst(
    base_url: str,
    *,
    path: str,
    ip: str,
    calls: int,
) -> Counter[int]:
    """Dispara ``calls`` chamadas CONCORRENTES (acha o limiar real de 429)."""
    statuses: Counter[int] = Counter()
    retry_after: str | None = None

    async def one(client: httpx.AsyncClient, index: int) -> None:
        nonlocal retry_after
        response = await client.get(
            path,
            params={"q": f"cap{index % 3}"},
            headers={"X-Forwarded-For": ip},
        )
        statuses[response.status_code] += 1
        if response.status_code == 429 and retry_after is None:
            retry_after = response.headers.get("retry-after")

    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:
        await asyncio.gather(*(one(client, index) for index in range(calls)))
    if retry_after is not None:
        print(f"    429 tem Retry-After: {retry_after}")
    return statuses


async def isolation_check(base_url: str, *, ip: str, calls: int) -> None:
    """Drena o balde SUGGEST do IP e verifica que SEARCH segue funcionando."""
    suggest: Counter[int] = Counter()
    products_status: int | None = None
    async with httpx.AsyncClient(base_url=base_url, timeout=15.0) as client:

        async def one(client: httpx.AsyncClient, index: int) -> None:
            response = await client.get(
                "/api/v1/search/suggest",
                params={"q": f"cap{index % 3}"},
                headers={"X-Forwarded-For": ip},
            )
            suggest[response.status_code] += 1

        await asyncio.gather(*(one(client, index) for index in range(calls)))
        products = await client.get(
            "/api/v1/search/products",
            params={"q": "cap"},
            headers={"X-Forwarded-For": ip},
        )
        products_status = products.status_code
    print(f"    suggest concorrente ({calls}): {dict(suggest)}")
    print(f"    /search/products no MESMO IP apos drenar o balde SUGGEST: {products_status}")
    if products_status != 200:
        print("    FALHA: balde SEARCH foi afetado pelo SUGGEST (nao deveria).")
        return False
    return True


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
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="cenario de pressao dispara as chamadas em paralelo (concorrente)",
    )
    parser.add_argument(
        "--isolation-check",
        type=int,
        default=0,
        help="drena o balde SUGGEST com N chamadas concorrentes e confere o /search/products",
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
            print(
                f"=== pressao: {args.stress_calls} chamadas "
                f"{'concurentes' if args.parallel else 'seguidas'} (IP dedicado) ==="
            )
            if args.parallel:
                statuses = asyncio.run(
                    parallel_burst(
                        args.base_url,
                        path="/api/v1/search/suggest",
                        ip="203.0.113.99",
                        calls=args.stress_calls,
                    )
                )
            else:
                statuses = burst(
                    client,
                    path="/api/v1/search/suggest",
                    ip="203.0.113.99",
                    calls=args.stress_calls,
                    interval_seconds=0.1,
                )
            print(f"IP 203.0.113.99 /suggest: {args.stress_calls} chamadas -> {dict(statuses)}")

        if args.isolation_check > 0:
            print(f"=== isolamento de baldes: {args.isolation_check} suggest concorrentes ===")
            isolado = asyncio.run(
                isolation_check(
                    args.base_url,
                    ip="203.0.113.60",
                    calls=args.isolation_check,
                )
            )
            if not isolado:
                return 1
            print("    OK: baldes independentes (SEARCH nao esgotou).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
