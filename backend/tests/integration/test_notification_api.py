"""Testes de integracao de notificacoes (outbox, despacho, opt-out, retries).

Usa PostgreSQL real (Testcontainers). Cobre: escrita transacional da outbox no
pedido, despacho por tenant com Fake email sender, opt-out, falha transitoria
(retry) vs permanente (dead-letter), enumeracao cross-tenant via SECURITY
DEFINER, e RBAC dos endpoints administrativos.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, cast

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher
from app.modules.notification.application.errors import EmailPermanentError, EmailTransientError
from app.modules.notification.application.notification import DispatchOutbox
from app.modules.notification.infrastructure.email import FakeEmailSender
from app.modules.notification.infrastructure.repository import SqlAlchemyNotificationRepository

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("bbbb0000-0000-4000-8000-000000000001")
_ADMIN = uuid.UUID("bbbb0000-0000-4000-8000-000000000002")
_BUYER = uuid.UUID("bbbb0000-0000-4000-8000-000000000003")
_ADMIN_MEMBER = uuid.UUID("bbbb0000-0000-4000-8000-000000000004")
_BUYER_MEMBER = uuid.UUID("bbbb0000-0000-4000-8000-000000000005")
_ADMIN_EMAIL = "notif-admin@teste.com"
_BUYER_EMAIL = "notif-buyer@teste.com"
_PASSWORD = "Senha@Forte123"
_LIMIT = Decimal("1000.00")

_CAT = uuid.UUID("bbbb0000-0000-4000-8000-000000000010")
_PRODUCT = uuid.UUID("bbbb0000-0000-4000-8000-000000000011")


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, '19999999000160', 'Notif Empresa', 'ACTIVE') "
            "ON CONFLICT (id) DO NOTHING",
            (_COMPANY,),
        )
        conn.execute(
            "INSERT INTO credit_accounts (company_id, credit_limit) "
            "VALUES (%s, %s) ON CONFLICT (company_id) DO NOTHING",
            (_COMPANY, _LIMIT),
        )
        for user_id, email, full_name in (
            (_ADMIN, _ADMIN_EMAIL, "Admin Notif"),
            (_BUYER, _BUYER_EMAIL, "Buyer Notif"),
        ):
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, password_hash, "
                "status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (user_id, _COMPANY, email, full_name, _cpf_hash(email), password_hash),
            )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'ADMIN', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_ADMIN_MEMBER, _COMPANY, _ADMIN),
        )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (_BUYER_MEMBER, _COMPANY, _BUYER),
        )
        for table in (
            "notification_preferences",
            "notifications",
            "payment_events",
            "payments",
            "invoices",
            "order_items",
            "orders",
            "credit_entries",
        ):
            conn.execute(f"DELETE FROM {table} WHERE company_id = %s", (_COMPANY,))
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'Notif Categoria', 'notif-categoria', true) "
            "ON CONFLICT (id) DO NOTHING",
            (_CAT,),
        )
        conn.execute(
            "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
            "base_unit_price, min_order_qty, weight_kg) VALUES (%s, %s, 'NOTIF-1', "
            "'Produto Notif', 'notif-1', 'ACTIVE', false, '10.00', 1, NULL) "
            "ON CONFLICT (id) DO NOTHING",
            (_PRODUCT, _CAT),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def notification_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def notification_env(
    test_settings: Settings, notification_seed: None
) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login", json={"email": _BUYER_EMAIL, "password": _PASSWORD}
        )
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield app, client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


async def _create_order(client: httpx.AsyncClient, key: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(_PRODUCT), "quantity": 1}],
            "payment_method": "PIX",
            "idempotency_key": key,
        },
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


class _TransientSender:
    async def send(self, *, to: str, subject: str, body: str) -> None:
        raise EmailTransientError("smtp unavailable")


class _PermanentSender:
    async def send(self, *, to: str, subject: str, body: str) -> None:
        raise EmailPermanentError("recipient refused")


async def test_pedido_escreve_outbox_e_despacho_envia_email(
    notification_env: tuple[Any, httpx.AsyncClient],
) -> None:
    app, client = notification_env
    await _create_order(client, "notif-order-1")

    repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    due = await repository.list_due(company_id=_COMPANY, limit=10, max_attempts=5)
    assert [d.event_type for d in due] == ["order.created"]

    sender = FakeEmailSender()
    use_case = DispatchOutbox(repository=repository, email_sender=sender)
    sent = await use_case.dispatch(company_id=_COMPANY, limit=10)
    assert sent == 1
    assert sender.sent[0]["to"] == _BUYER_EMAIL

    remaining = await repository.list_due(company_id=_COMPANY, limit=10, max_attempts=5)
    assert remaining == []


async def test_opt_out_pula_envio(
    notification_env: tuple[Any, httpx.AsyncClient], pg: PostgresInstance
) -> None:
    app, client = notification_env
    await _create_order(client, "notif-order-2")

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_COMPANY,))
        conn.execute(
            "INSERT INTO notification_preferences (company_id, user_id, channel, enabled) "
            "VALUES (%s, %s, 'EMAIL', false) ON CONFLICT (company_id, user_id, channel) "
            "DO UPDATE SET enabled = false",
            (_COMPANY, _BUYER),
        )
        conn.commit()
    finally:
        conn.close()

    repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    sender = FakeEmailSender()
    sent = await DispatchOutbox(repository=repository, email_sender=sender).dispatch(
        company_id=_COMPANY, limit=10
    )
    assert sent == 0
    assert sender.sent == []

    notifications = await repository.list_notifications(_COMPANY)
    assert notifications[0].status == "SKIPPED"


async def test_falha_permanente_vai_para_dead_letter(
    notification_env: tuple[Any, httpx.AsyncClient],
) -> None:
    app, client = notification_env
    await _create_order(client, "notif-order-3")

    repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    use_case = DispatchOutbox(repository=repository, email_sender=_PermanentSender())
    sent = await use_case.dispatch(company_id=_COMPANY, limit=10)
    assert sent == 0

    notifications = await repository.list_notifications(_COMPANY)
    assert notifications[0].status == "DEAD_LETTERED"


async def test_falha_transitoria_retenta(
    notification_env: tuple[Any, httpx.AsyncClient],
) -> None:
    app, client = notification_env
    await _create_order(client, "notif-order-4")

    repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    use_case = DispatchOutbox(repository=repository, email_sender=_TransientSender())
    sent = await use_case.dispatch(company_id=_COMPANY, limit=10)
    assert sent == 0

    notifications = await repository.list_notifications(_COMPANY)
    assert notifications[0].status == "FAILED"
    assert notifications[0].attempts == 1


async def test_list_due_tenants_via_security_definer(
    notification_env: tuple[Any, httpx.AsyncClient],
) -> None:
    app, client = notification_env
    await _create_order(client, "notif-order-5")

    repository = SqlAlchemyNotificationRepository(app.state.uow_factory)
    tenants = await repository.list_due_tenants(limit=100, max_attempts=5)
    assert _COMPANY in tenants


async def test_admin_list_resend_rbac(notification_env: tuple[Any, httpx.AsyncClient]) -> None:
    _app, client = notification_env
    await _create_order(client, "notif-order-6")

    # BUYER nao pode listar (403).
    list_resp = await client.get("/api/v1/notifications")
    assert list_resp.status_code == 403

    # ADMIN pode listar e reenviar.
    admin_login = await client.post(
        "/api/v1/auth/login", json={"email": _ADMIN_EMAIL, "password": _PASSWORD}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    list_resp = await client.get("/api/v1/notifications", headers=admin_headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body and body[0]["event_type"] == "order.created"

    notification_id = body[0]["id"]
    resend_resp = await client.post(
        f"/api/v1/notifications/{notification_id}/resend", headers=admin_headers
    )
    assert resend_resp.status_code == 204
