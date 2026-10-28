"""Adaptadores do canal de e-mail (Fake local, SMTP Mailpit e Resend HTTP).

Nenhum servico pago e obrigatorio: o adaptador SMTP envia para o Mailpit local
(SMTP fake, padrao em dev) e o Fake apenas registra em memoria para
reproducibilidade em testes. `ResendEmailSender` (item 2) chama a API HTTP do
Resend quando `EMAIL_PROVIDER=resend` — a chave fica SOMENTE no backend,
NUNCA e logada e o corpo/destinatario nao entram em mensagens de erro.
Retry fica no mecanismo existente do outbox (FAILED + max_attempts).
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import Settings
from app.modules.notification.application.errors import EmailPermanentError, EmailTransientError
from app.modules.notification.application.ports import EmailSender

_RESEND_BASE_URL = "https://api.resend.com"


class FakeEmailSender:
    """Registra envios em memoria (deterministico, para testes)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str | None]] = []

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body, "html": html})


class SmtpEmailSender:
    """Envia e-mails via SMTP local (Mailpit). Sem autenticacao/segredos."""

    def __init__(self, *, host: str, port: int, from_email: str, timeout: int = 10) -> None:
        self._host = host
        self._port = port
        self._from_email = from_email
        self._timeout = timeout

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body, html)

    def _send_sync(self, to: str, subject: str, body: str, html_body: str | None) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._from_email
        msg["To"] = to
        msg.set_content(body)
        if html_body:
            # multipart/alternative: texto puro + HTML (valor JA escapado no render).
            msg.add_alternative(html_body, subtype="html")
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailPermanentError("recipient refused") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailTransientError("smtp unavailable") from exc


class ResendEmailSender:
    """Envia e-mails pela API HTTP do Resend (qualquer provedor compativel).

    Sem retry proprio (o outbox retenta com o mecanismo existente); timeout
    curto; erros com mensagem estatica — nunca corpo, destinatario ou chave.
    """

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._from_email = from_email
        self._client = httpx.AsyncClient(
            base_url=_RESEND_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def send(self, *, to: str, subject: str, body: str, html: str | None = None) -> None:
        payload: dict[str, object] = {
            "from": self._from_email,
            "to": [to],
            "subject": subject,
            "text": body,
        }
        if html:
            payload["html"] = html
        try:
            response = await self._client.post("/emails", json=payload)
        except httpx.TimeoutException as exc:
            raise EmailTransientError("email provider timeout") from exc
        except httpx.HTTPError as exc:
            raise EmailTransientError("email provider unavailable") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise EmailTransientError("email provider busy")
        if response.status_code >= 400:
            raise EmailPermanentError("email rejected")

    async def aclose(self) -> None:
        await self._client.aclose()


def build_email_sender(settings: Settings) -> EmailSender:
    """Fabrica por EMAIL_PROVIDER: 'smtp' (Mailpit, padrao dev) ou 'resend'."""
    if settings.email_provider == "resend":
        if not settings.resend_api_key or not settings.resend_from:
            raise EmailPermanentError("email provider misconfigured")
        return ResendEmailSender(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from,
            timeout=10.0,
        )
    return SmtpEmailSender(
        host=settings.email_smtp_host,
        port=settings.email_smtp_port,
        from_email=settings.email_from,
    )
