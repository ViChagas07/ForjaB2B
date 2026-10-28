"""Testes do canal WhatsApp (Fase 3, item 3) — NENHUM teste chama rede."""

import httpx
import pytest

from app.core.config import Settings
from app.modules.notification.application.errors import EmailPermanentError, EmailTransientError
from app.modules.notification.application.notification import DispatchOutbox, is_e164
from app.modules.notification.application.ports import OutboxView, RecipientView
from app.modules.notification.domain.enums import NotificationStatus
from app.modules.notification.infrastructure.email import FakeEmailSender
from app.modules.notification.infrastructure.whatsapp import (
    ZApiWhatsAppSender,
    build_whatsapp_sender,
)
import uuid
from datetime import UTC, datetime


class FakeRepo:
    """Repositorio fake: devolve o destinatario configurado e marca status."""

    def __init__(self, recipient: RecipientView | None) -> None:
        self.recipient = recipient
        self.statuses: list[NotificationStatus] = []

    async def list_due(self, *, company_id: object, limit: int, max_attempts: int) -> list[OutboxView]:
        return [
            OutboxView(
                id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                event_type="cart.recovery",
                aggregate_id=uuid.uuid4(),
                payload={
                    "company_name": "Metalúrgica Alfa",
                    "items_summary": "- 2x Capacete Pro (CAP-001)",
                    "offer_text": "Frete grátis",
                    "personal_note": "estoque limitado",
                },
                status="PENDING",
                attempts=0,
                created_at=datetime.now(UTC),
                channel="WHATSAPP",
            )
        ]

    async def list_due_tenants(self, *, limit: int, max_attempts: int) -> set[uuid.UUID]:
        return set()

    async def resolve_recipient(
        self, *, company_id: object, event_type: str, aggregate_id: uuid.UUID, channel: str = "EMAIL"
    ) -> RecipientView | None:
        return self.recipient

    async def mark(self, *, company_id: object, outbox_id: uuid.UUID, status: NotificationStatus, error: str | None = None) -> None:
        self.statuses.append(status)

    async def list_notifications(self, company_id: object) -> list[OutboxView]:
        return []

    async def get_notification(self, company_id: object, outbox_id: uuid.UUID) -> OutboxView | None:
        return None

    async def reset_for_resend(self, company_id: object, outbox_id: uuid.UUID) -> None:
        return None


class FakeWhatsApp:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, *, phone: str, message: str) -> None:
        self.sent.append((phone, message))


def recipient(*, phone: str | None = "+5511998765432", opt_in: bool = True) -> RecipientView:
    return RecipientView(
        email="cliente@empresa.test",
        locale="pt-BR",
        opted_out=False,
        user_id=uuid.uuid4(),
        whatsapp_phone=phone,
        whatsapp_opt_in=opt_in,
    )


def make_dispatch(whatsapp: FakeWhatsApp | None, repo: FakeRepo) -> DispatchOutbox:
    return DispatchOutbox(
        repository=repo,
        email_sender=FakeEmailSender(),
        whatsapp_sender=whatsapp,
        frontend_base_url="https://forja.example",
    )


async def test_whatsapp_sem_opt_in_e_pulado() -> None:
    whatsapp = FakeWhatsApp()
    repo = FakeRepo(recipient(opt_in=False))
    sent = await make_dispatch(whatsapp, repo).dispatch(company_id=uuid.uuid4())
    assert sent == 0
    assert whatsapp.sent == []
    assert repo.statuses == [NotificationStatus.SKIPPED]


async def test_whatsapp_sem_numero_valido_e_pulado() -> None:
    whatsapp = FakeWhatsApp()
    repo = FakeRepo(recipient(phone="1198765432"))  # sem "+", nao e E.164
    sent = await make_dispatch(whatsapp, repo).dispatch(company_id=uuid.uuid4())
    assert sent == 0
    assert whatsapp.sent == []
    assert repo.statuses == [NotificationStatus.SKIPPED]


async def test_whatsapp_desligado_e_pulado() -> None:
    repo = FakeRepo(recipient())
    sent = await make_dispatch(None, repo).dispatch(company_id=uuid.uuid4())
    assert sent == 0
    assert repo.statuses == [NotificationStatus.SKIPPED]


async def test_whatsapp_envia_com_optin_e_e164() -> None:
    whatsapp = FakeWhatsApp()
    repo = FakeRepo(recipient())
    sent = await make_dispatch(whatsapp, repo).dispatch(company_id=uuid.uuid4())
    assert sent == 1
    assert repo.statuses == [NotificationStatus.SENT]
    phone, message = whatsapp.sent[0]
    assert phone == "+5511998765432"
    assert "Metalúrgica Alfa" in message
    assert "https://forja.example/pt-BR/cart" in message  # link do backend
    assert "estoque limitado" in message


def test_is_e164() -> None:
    assert is_e164("+5511998765432")
    assert not is_e164("5511998765432")
    assert not is_e164("+55 11 98765-432")
    assert not is_e164("+5511")


def test_fabrica_whatsapp_desligada_por_padrao() -> None:
    assert build_whatsapp_sender(Settings(_env_file=None)) is None
    with pytest.raises(EmailPermanentError):
        build_whatsapp_sender(Settings(whatsapp_enabled=True, _env_file=None))


def test_zapi_envia_com_client_token_header() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"success": True})

    sender = ZApiWhatsAppSender(
        instance_id="INSTANCE",
        token="TOKEN123",
        client_token="CLIENT-SECRET",
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        await sender.send(phone="+5511998765432", message="oi")

    __import__("asyncio").run(run())
    request = captured[0]
    assert request.url.path == "/instances/INSTANCE/token/TOKEN123/send-text"
    assert request.headers["Client-Token"] == "CLIENT-SECRET"


def test_zapi_5xx_e_transient() -> None:
    sender = ZApiWhatsAppSender(
        instance_id="I",
        token="T",
        client_token="C",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )

    async def run() -> None:
        with pytest.raises(EmailTransientError):
            await sender.send(phone="+5511998765432", message="oi")

    __import__("asyncio").run(run())
