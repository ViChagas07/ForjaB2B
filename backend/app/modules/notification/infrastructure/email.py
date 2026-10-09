"""Adaptadores do canal de e-mail (Fake local e SMTP Mailpit).

Nenhum servico pago: o adaptador SMTP envia para o Mailpit local (SMTP fake) e
o Fake apenas registra em memoria para reproducibilidade em testes.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.modules.notification.application.errors import EmailPermanentError, EmailTransientError


class FakeEmailSender:
    """Registra envios em memoria (deterministico, para testes)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


class SmtpEmailSender:
    """Envia e-mails via SMTP local (Mailpit). Sem autenticacao/segredos."""

    def __init__(self, *, host: str, port: int, from_email: str, timeout: int = 10) -> None:
        self._host = host
        self._port = port
        self._from_email = from_email
        self._timeout = timeout

    async def send(self, *, to: str, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body)

    def _send_sync(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._from_email
        msg["To"] = to
        msg.set_content(body)
        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailPermanentError("recipient refused") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailTransientError("smtp unavailable") from exc
