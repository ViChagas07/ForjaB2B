"""Smoke test de producao da busca do catalogo (somente leitura). Fase 6.

Roda contra uma URL configuravel e valida: health da aplicacao e do Elasticsearch
(separados); consulta por SKU; consulta textual sem acento; consulta semantica;
preco consultivo para visitante; e o modo de busca informado. Nao grava, nao
apaga e nao imprime segredos (o token nunca e exibido).

Uso:
    python backend/scripts/smoke_search.py --base-url https://api.exemplo.com \
        --sku CAP-001 --text capacete --semantic "protecao para solda"
    # preco do autenticado (opcional, via env para nao vazar em `ps`):
    SMOKE_TOKEN=<access-token> python backend/scripts/smoke_search.py ...
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import httpx

_DEGRADED_MODES = {"semantic_postgres", "postgres_fallback"}


@dataclass(frozen=True)
class _Result:
    name: str
    ok: bool
    detail: str


def _check(name: str, ok: bool, detail: str) -> _Result:
    return _Result(name=name, ok=ok, detail=detail)


def _search(client: httpx.Client, params: dict[str, str]) -> tuple[int, dict[str, object]]:
    response = client.get("/api/v1/search/products", params=params)
    payload: dict[str, object] = response.json() if response.content else {}
    return response.status_code, payload


def run(
    base_url: str,
    *,
    sku: str | None,
    text: str,
    semantic: str,
    token: str | None,
    timeout: float,
) -> int:
    results: list[_Result] = []
    modes: dict[str, str] = {}
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    with httpx.Client(base_url=base_url, timeout=timeout, headers=headers) as client:
        live = client.get("/health/live")
        results.append(
            _check(
                "health/live",
                live.status_code == 200 and live.json().get("status") == "alive",
                f"http={live.status_code}",
            )
        )

        health = client.get("/health/search")
        state = str(health.json().get("status")) if health.status_code == 200 else "?"
        results.append(
            _check(
                "health/search",
                health.status_code == 200 and state in {"ok", "degraded", "disabled"},
                f"status={state}",
            )
        )

        if sku:
            status, body = _search(client, {"q": sku})
            mode = str(body.get("search_mode", "?"))
            modes["sku"] = mode
            items = body.get("items", [])
            found = isinstance(items, list) and any(
                str(item.get("sku", "")).upper() == sku.upper()
                for item in items
                if isinstance(item, dict)
            )
            results.append(
                _check("busca por SKU", status == 200 and found, f"http={status} mode={mode}")
            )

        status, body = _search(client, {"q": text})
        mode = str(body.get("search_mode", "?"))
        modes["texto"] = mode
        text_items = body.get("items", [])
        results.append(
            _check("busca textual (sem acento)", status == 200, f"http={status} mode={mode}")
        )

        status, body = _search(client, {"q": semantic})
        modes["semantico"] = str(body.get("search_mode", "?"))
        results.append(
            _check(
                "busca semantica",
                status == 200,
                f"http={status} mode={modes['semantico']}",
            )
        )

        if isinstance(text_items, list) and text_items:
            visitor_ok = all(
                isinstance(item, dict)
                and item.get("price_on_request") is True
                and item.get("base_unit_price") is None
                for item in text_items
            )
            results.append(
                _check("preco consultivo para visitante", visitor_ok, f"itens={len(text_items)}")
            )
        else:
            results.append(_check("preco consultivo para visitante", True, "sem itens"))

        if token:
            status, body = _search(client, {"q": text})
            auth_items = body.get("items", [])
            if isinstance(auth_items, list) and auth_items:
                auth_ok = all(
                    isinstance(item, dict) and item.get("price_on_request") is False
                    for item in auth_items
                )
                results.append(_check("preco do autenticado", auth_ok, f"itens={len(auth_items)}"))
            else:
                results.append(_check("preco do autenticado", status == 200, "sem itens"))

    print(f"Smoke test da busca em {base_url}")
    for result in results:
        print(f"  [{'PASS' if result.ok else 'FAIL'}] {result.name} :: {result.detail}")
    print("Modos observados: " + ", ".join(f"{key}={value}" for key, value in modes.items()))
    degraded = sorted({value for value in modes.values() if value in _DEGRADED_MODES})
    if degraded:
        print(f"AVISO: busca em modo degradado: {', '.join(degraded)}")

    failed = [result.name for result in results if not result.ok]
    if failed:
        print("FALHAS: " + ", ".join(failed))
        return 1
    print("OK: smoke test da busca aprovado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test somente-leitura da busca.")
    parser.add_argument(
        "--base-url", default=os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--sku", default=os.environ.get("SMOKE_SKU"))
    parser.add_argument("--text", default="capacete")
    parser.add_argument("--semantic", default="protecao para solda")
    parser.add_argument("--token", default=os.environ.get("SMOKE_TOKEN"))
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    return run(
        args.base_url,
        sku=args.sku,
        text=args.text,
        semantic=args.semantic,
        token=args.token,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
