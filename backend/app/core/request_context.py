"""Contexto de rede da requisicao: IP real e esquema atras de proxies.

`X-Forwarded-For` e `X-Forwarded-Proto` so sao considerados quando existe uma
quantidade configurada de proxies confiaveis (`TRUSTED_PROXY_COUNT`). O IP
escolhido e o primeiro nao confiavel da direita para a esquerda; valores
malformados caem no IP da conexao (fail-safe). Nenhum dado de PII e logado.
"""

from __future__ import annotations

import ipaddress
from collections.abc import MutableMapping
from typing import Any

_FORWARDED_FOR = b"x-forwarded-for"
_FORWARDED_PROTO = b"x-forwarded-proto"
_UNKNOWN_IP = "unknown"


def _header(scope: MutableMapping[str, Any], name: bytes) -> str | None:
    for key, value in scope.get("headers") or []:
        if key.lower() == name:
            raw = str(value.decode("latin-1") if isinstance(value, (bytes, bytearray)) else value)
            return raw.strip()
    return None


def _peer_ip(scope: MutableMapping[str, Any]) -> str:
    client = scope.get("client")
    if isinstance(client, tuple) and client:
        host = client[0]
        if isinstance(host, str) and host:
            return host
    return _UNKNOWN_IP


def client_ip(scope: MutableMapping[str, Any], trusted_proxy_count: int) -> str:
    """IP do cliente, confiando em XFF apenas dos proxies configurados.

    Com ``trusted_proxy_count=1`` (Render), o XFF recebido tem o cliente na
    ultima posicao (`cliente` ou `cliente, proxy`). Com N proxies, usa-se a
    N-esima entrada a partir da direita; se a cadeia for menor, usa o peer.
    """
    peer = _peer_ip(scope)
    if trusted_proxy_count <= 0:
        return peer

    forwarded = _header(scope, _FORWARDED_FOR)
    if not forwarded:
        return peer

    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(parts) < trusted_proxy_count:
        return peer

    candidate = parts[-trusted_proxy_count]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer


def request_scheme(scope: MutableMapping[str, Any], trusted_proxy_count: int) -> str:
    """Esquema efetivo; aceita X-Forwarded-Proto apenas de proxy confiavel."""
    scheme = scope.get("scheme")
    base = scheme if isinstance(scheme, str) and scheme else "http"
    if trusted_proxy_count <= 0:
        return base
    forwarded = _header(scope, _FORWARDED_PROTO)
    if forwarded is None:
        return base
    first = forwarded.split(",")[0].strip().lower()
    if first in {"http", "https"}:
        return first
    return base
