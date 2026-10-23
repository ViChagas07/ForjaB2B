"""Utilitarios de webhooks: corpo limitado e verificacao HMAC.

Segredos e assinaturas nunca sao registrados em log. A comparacao e feita em
tempo constante (``hmac.compare_digest``) e itera TODOS os segredos ativos, sem
curto-circuito, para suportar rotacao sem janela de falha.
"""

from __future__ import annotations

import hmac
import time
from hashlib import sha256

from fastapi import Request

from app.core.errors import AppError

SIGNATURE_PREFIX = "sha256="


class WebhookPayloadTooLargeError(AppError):
    """Corpo do webhook acima do limite configurado."""

    status_code = 413
    title = "Content Too Large"
    code = "webhook_payload_too_large"


class WebhookSignatureError(AppError):
    """Assinatura ausente/invalida; resposta generica, sem detalhes."""

    status_code = 401
    title = "Unauthorized"
    code = "invalid_webhook_signature"


class WebhookTimestampError(AppError):
    """Timestamp ausente/invalido ou fora da tolerancia (anti-replay)."""

    status_code = 401
    title = "Unauthorized"
    code = "webhook_timestamp_invalid"


async def read_limited_body(request: Request, max_bytes: int) -> bytes:
    """Le o corpo bruto em chunks, recusando acima de ``max_bytes``.

    O stream e lido antes de qualquer parse (a assinatura cobre os bytes
    originais). ``Content-Length`` antecipa a recusa quando informado.
    """
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = 0
        if declared > max_bytes:
            raise WebhookPayloadTooLargeError(f"Corpo do webhook excede {max_bytes} bytes.")

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise WebhookPayloadTooLargeError(f"Corpo do webhook excede {max_bytes} bytes.")
        chunks.append(chunk)
    return b"".join(chunks)


def _any_secret_matches(*, secrets: list[str], signed: bytes, provided: str) -> bool:
    matched = False
    for secret in secrets:
        expected = hmac.new(secret.encode(), signed, sha256).hexdigest()
        # |= mantem a comparacao de todos os segredos (rotacao sem curto-circuito).
        matched |= hmac.compare_digest(expected, provided)
    return matched


def verify_hmac_signature(
    *,
    secrets: list[str],
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    tolerance_seconds: int,
    now: float | None = None,
) -> None:
    """Valida ``sha256=<hex>`` sobre o corpo (ou sobre ``timestamp.body``).

    - Com ``X-Forja-Timestamp``: a assinatura cobre ``<timestamp>.<body>`` e o
      timestamp precisa estar dentro da tolerancia (anti-replay).
    - Sem timestamp: aceita apenas a assinatura legada sobre o corpo, para nao
      quebrar produtores antigos durante a janela de depreciacao.
    """
    if not signature or not signature.startswith(SIGNATURE_PREFIX):
        raise _signature_error()

    provided = signature[len(SIGNATURE_PREFIX) :]
    if timestamp is not None:
        try:
            parsed = int(timestamp)
        except ValueError as exc:
            raise WebhookTimestampError("Timestamp do webhook invalido.") from exc
        current = time.time() if now is None else now
        if abs(current - parsed) > tolerance_seconds:
            raise WebhookTimestampError("Timestamp do webhook fora da tolerancia.")
        signed = f"{parsed}.".encode() + body
    else:
        signed = body

    if not secrets or not _any_secret_matches(secrets=secrets, signed=signed, provided=provided):
        raise _signature_error()


def _signature_error() -> AppError:
    return WebhookSignatureError()
