"""Desconto automatico CNPJ no carrinho, checkout e pedido (PostgreSQL real).

Valida a regra por produto (15% e 30% a partir de 30 unidades), a resposta por
item, o snapshot do pedido, a interacao com cupom e a recusa de preco/percentual
enviados pelo cliente. Empresas CPF (PERSON) mantem o preco atual.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_CNPJ_COMPANY = uuid.UUID("fafa0000-0000-4000-8000-000000000001")
_CNPJ_USER = uuid.UUID("fafa0000-0000-4000-8000-000000000002")
_CNPJ_MEMBER = uuid.UUID("fafa0000-0000-4000-8000-000000000003")
_PERSON_COMPANY = uuid.UUID("fafa0000-0000-4000-8000-000000000011")
_PERSON_USER = uuid.UUID("fafa0000-0000-4000-8000-000000000012")
_PERSON_MEMBER = uuid.UUID("fafa0000-0000-4000-8000-000000000013")

_CNPJ_EMAIL = "cnpj-discount@teste.com"
_PERSON_EMAIL = "cpf-discount@teste.com"
_PASSWORD = "Senha@Forte123"

_CATEGORY = uuid.UUID("fafa0000-0000-4000-8000-000000000021")
_PRODUCT_A = uuid.UUID("fafa0000-0000-4000-8000-000000000022")
_PRODUCT_B = uuid.UUID("fafa0000-0000-4000-8000-000000000023")
_PRODUCT_ROUNDING = uuid.UUID("fafa0000-0000-4000-8000-000000000024")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    password_hash = Argon2PasswordHasher().hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        for company_id, legal_name, cnpj in (
            (_CNPJ_COMPANY, "CNPJ Desconto Empresa", "99888777000282"),
            (_PERSON_COMPANY, "CPF Desconto Empresa", None),
        ):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            if cnpj is None:
                conn.execute(
                    "INSERT INTO companies (id, legal_name, status, account_type) "
                    "VALUES (%s, %s, 'ACTIVE', 'PERSON') ON CONFLICT (id) DO NOTHING",
                    (company_id, legal_name),
                )
            else:
                conn.execute(
                    "INSERT INTO companies (id, cnpj, legal_name, status, account_type) "
                    "VALUES (%s, %s, %s, 'ACTIVE', 'COMPANY') ON CONFLICT (id) DO NOTHING",
                    (company_id, cnpj, legal_name),
                )

        for company_id, user_id, member_id, email in (
            (_CNPJ_COMPANY, _CNPJ_USER, _CNPJ_MEMBER, _CNPJ_EMAIL),
            (_PERSON_COMPANY, _PERSON_USER, _PERSON_MEMBER, _PERSON_EMAIL),
        ):
            conn.execute("SELECT app.set_tenant_context(%s, NULL)", (company_id,))
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, "
                "password_hash, status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') "
                "ON CONFLICT (id) DO NOTHING",
                (user_id, company_id, email, email, _hash(email), password_hash),
            )
            conn.execute(
                "INSERT INTO company_members (id, company_id, user_id, role, status) "
                "VALUES (%s, %s, %s, 'BUYER', 'ACTIVE') ON CONFLICT (id) DO NOTHING",
                (member_id, company_id, user_id),
            )
            conn.execute("DELETE FROM carts WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM payment_events WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM payments WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM coupon_redemptions WHERE company_id = %s", (company_id,))
            conn.execute(
                "DELETE FROM order_item_pricing WHERE order_item_id IN "
                "(SELECT id FROM order_items WHERE company_id = %s)",
                (company_id,),
            )
            conn.execute("DELETE FROM order_items WHERE company_id = %s", (company_id,))
            conn.execute("DELETE FROM orders WHERE company_id = %s", (company_id,))
        conn.commit()
    finally:
        conn.close()

    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute(
            "INSERT INTO categories (id, name, slug, is_active) "
            "VALUES (%s, 'CNPJ Desconto', 'cnpj-desconto', true) ON CONFLICT (id) DO NOTHING",
            (_CATEGORY,),
        )
        for product_id, sku, name, price in (
            (_PRODUCT_A, "CNPJ-A", "Luva CNPJ", "100.00"),
            (_PRODUCT_B, "CNPJ-B", "Oculos CNPJ", "100.00"),
            (_PRODUCT_ROUNDING, "CNPJ-R", "Produto Arredondamento", "24.90"),
        ):
            conn.execute(
                "INSERT INTO products (id, category_id, sku, name, slug, status, is_epi, "
                "base_unit_price, min_order_qty) VALUES (%s, %s, %s, %s, %s, 'ACTIVE', "
                "false, %s, 1) ON CONFLICT (id) DO NOTHING",
                (product_id, _CATEGORY, sku, name, sku.lower(), price),
            )
        conn.execute(
            "INSERT INTO coupons (code, type, percent, is_active, created_by) "
            "VALUES ('CNPJ10', 'PRODUCT_TOTAL', 10.00, true, %s) "
            "ON CONFLICT (code) DO NOTHING",
            (_CNPJ_USER,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def cnpj_seed(pg: PostgresInstance, migrated_domain_schema: None) -> Iterator[None]:
    _seed(pg, migrated_domain_schema)
    yield
    # Cupons sao globais: nao podem vazar para os testes de admin/cupom.
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_CNPJ_COMPANY,))
        conn.execute("DELETE FROM coupon_redemptions WHERE company_id = %s", (_CNPJ_COMPANY,))
        conn.execute("DELETE FROM coupons WHERE code = 'CNPJ10'")
        conn.execute("DELETE FROM payment_events WHERE company_id = %s", (_CNPJ_COMPANY,))
        conn.execute("DELETE FROM payments WHERE company_id = %s", (_CNPJ_COMPANY,))
        conn.execute(
            "DELETE FROM order_item_pricing WHERE order_item_id IN "
            "(SELECT id FROM order_items WHERE company_id = %s)",
            (_CNPJ_COMPANY,),
        )
        conn.execute("DELETE FROM order_items WHERE company_id = %s", (_CNPJ_COMPANY,))
        conn.execute("DELETE FROM orders WHERE company_id = %s", (_CNPJ_COMPANY,))
        conn.execute("DELETE FROM carts WHERE company_id = %s", (_CNPJ_COMPANY,))
        conn.execute(
            "DELETE FROM order_item_pricing WHERE order_item_id IN "
            "(SELECT id FROM order_items WHERE company_id = %s)",
            (_PERSON_COMPANY,),
        )
        conn.execute("DELETE FROM order_items WHERE company_id = %s", (_PERSON_COMPANY,))
        conn.execute("DELETE FROM orders WHERE company_id = %s", (_PERSON_COMPANY,))
        conn.execute("DELETE FROM carts WHERE company_id = %s", (_PERSON_COMPANY,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
async def cnpj_api(
    test_settings: Settings, cnpj_seed: None
) -> AsyncIterator[tuple[httpx.AsyncClient, httpx.AsyncClient]]:
    app = create_app(test_settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as cnpj_client,
        httpx.AsyncClient(transport=transport, base_url="http://test") as person_client,
    ):
        cnpj_login = await cnpj_client.post(
            "/api/v1/auth/login", json={"email": _CNPJ_EMAIL, "password": _PASSWORD}
        )
        person_login = await person_client.post(
            "/api/v1/auth/login", json={"email": _PERSON_EMAIL, "password": _PASSWORD}
        )
        cnpj_client.headers["Authorization"] = f"Bearer {cnpj_login.json()['access_token']}"
        person_client.headers["Authorization"] = f"Bearer {person_login.json()['access_token']}"
        yield cnpj_client, person_client
    await app.state.db_engine.dispose()
    await close_redis_client(app.state.redis_client)


def _item(product_id: uuid.UUID, quantity: int) -> dict[str, object]:
    return {"product_id": str(product_id), "quantity": quantity}


async def test_cnpj_1_unidade_aplica_15_e_expoe_snapshot(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 1}
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["list_unit_price"] == "100.00"
    assert item["discount_percent"] == "15.00"
    assert item["discount_band"] == 15
    assert item["units_to_volume_discount"] == 29
    assert item["unit_price"] == "85.00"
    assert item["line_total"] == "85.00"
    assert item["list_line_total"] == "100.00"
    assert item["discount_amount"] == "15.00"
    assert response.json()["subtotal"] == "85.00"
    assert response.json()["list_subtotal"] == "100.00"
    assert response.json()["cnpj_discount_total"] == "15.00"


async def test_cnpj_29_unidades_fica_a_1_da_faixa(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 29}
    )
    item = response.json()["items"][0]
    assert item["discount_percent"] == "15.00"
    assert item["discount_band"] == 15
    assert item["units_to_volume_discount"] == 1
    assert item["unit_price"] == "85.00"


async def test_cnpj_30_unidades_aplica_30(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 30}
    )
    item = response.json()["items"][0]
    assert item["discount_percent"] == "30.00"
    assert item["discount_band"] == 30
    assert item["units_to_volume_discount"] is None
    assert item["unit_price"] == "70.00"
    assert item["line_total"] == "2100.00"
    assert item["list_line_total"] == "3000.00"
    assert item["discount_amount"] == "900.00"
    assert response.json()["list_subtotal"] == "3000.00"
    assert response.json()["cnpj_discount_total"] == "900.00"


async def test_cnpj_31_unidades_continua_em_30(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 31}
    )
    item = response.json()["items"][0]
    assert item["discount_percent"] == "30.00"
    assert item["discount_band"] == 30
    assert item["unit_price"] == "70.00"


async def test_dois_produtos_10_mais_20_ficam_cada_um_em_15(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 10}
    )
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_B), "quantity": 20}
    )
    items = {item["sku"]: item for item in response.json()["items"]}
    assert items["CNPJ-A"]["discount_band"] == 15
    assert items["CNPJ-B"]["discount_band"] == 15
    assert items["CNPJ-A"]["unit_price"] == "85.00"
    assert items["CNPJ-B"]["unit_price"] == "85.00"
    assert response.json()["subtotal"] == "2550.00"
    assert response.json()["list_subtotal"] == "3000.00"
    assert response.json()["cnpj_discount_total"] == "450.00"

    preview = await cnpj_client.post(
        "/api/v1/orders/coupon-preview", json={"payment_method": "CARD"}
    )
    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["subtotal"] == response.json()["subtotal"] == "2550.00"
    assert preview_body["total"] == "2550.00"
    assert preview_body["cnpj_discount_total"] == "450.00"


async def test_produto_30_mais_outro_10_aplica_faixas_diferentes(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 30}
    )
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_B), "quantity": 10}
    )
    items = {item["sku"]: item for item in response.json()["items"]}
    assert items["CNPJ-A"]["discount_band"] == 30
    assert items["CNPJ-A"]["unit_price"] == "70.00"
    assert items["CNPJ-B"]["discount_band"] == 15
    assert items["CNPJ-B"]["unit_price"] == "85.00"
    assert response.json()["subtotal"] == "2950.00"
    assert response.json()["cnpj_discount_total"] == "1050.00"

    preview = await cnpj_client.post(
        "/api/v1/orders/coupon-preview", json={"payment_method": "CARD"}
    )
    assert preview.status_code == 200
    assert preview.json()["subtotal"] == "2950.00"
    assert preview.json()["total"] == response.json()["subtotal"]


async def test_cpf_nao_recebe_desconto(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    _, person_client = cnpj_api
    response = await person_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 30}
    )
    item = response.json()["items"][0]
    assert item["list_unit_price"] == "100.00"
    assert item["discount_percent"] == "0.00"
    assert item["discount_band"] is None
    assert item["units_to_volume_discount"] is None
    assert item["unit_price"] == "100.00"
    assert item["discount_amount"] == "0.00"
    assert response.json()["subtotal"] == "3000.00"
    assert response.json()["list_subtotal"] == "3000.00"
    assert response.json()["cnpj_discount_total"] == "0.00"

    preview = await person_client.post(
        "/api/v1/orders/coupon-preview", json={"payment_method": "CARD"}
    )
    assert preview.status_code == 200
    assert preview.json()["subtotal"] == "3000.00"
    assert preview.json()["total"] == "3000.00"
    assert preview.json()["cnpj_discount_total"] == "0.00"


async def test_catalogo_cnpj_expoe_tabela_e_preco_com_15(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.get("/api/v1/catalog/products", params={"q": "CNPJ-A"})
    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["sku"] == "CNPJ-A")
    assert item["list_unit_price"] == "100.00"
    assert item["unit_price"] == "85.00"
    assert item["base_unit_price"] == "85.00"
    assert item["discount_percent"] == "15.00"
    assert item["discount_band"] == 15

    detail = await cnpj_client.get(f"/api/v1/catalog/products/{_PRODUCT_A}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["list_unit_price"] == "100.00"
    assert detail_body["unit_price"] == "85.00"
    assert detail_body["discount_band"] == 15


async def test_catalogo_cpf_nao_expoe_desconto(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    _, person_client = cnpj_api
    response = await person_client.get("/api/v1/catalog/products", params={"q": "CNPJ-A"})
    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["sku"] == "CNPJ-A")
    assert item["list_unit_price"] == "100.00"
    assert item["unit_price"] == "100.00"
    assert item["discount_percent"] == "0.00"
    assert item["discount_band"] is None


async def test_arredondamento_de_centavos_no_carrinho(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_ROUNDING), "quantity": 1}
    )
    item = response.json()["items"][0]
    assert item["list_unit_price"] == "24.90"
    assert item["unit_price"] == "21.17"


async def test_preview_de_cupom_incide_sobre_valor_cnpj(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    await cnpj_client.post(
        "/api/v1/cart/items", json={"product_id": str(_PRODUCT_A), "quantity": 1}
    )
    response = await cnpj_client.post(
        "/api/v1/orders/coupon-preview",
        json={"code": "CNPJ10", "payment_method": "CARD"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["subtotal"] == "85.00"
    assert body["list_subtotal"] == "100.00"
    assert body["cnpj_discount_total"] == "15.00"
    assert body["coupon_discount"] == "8.50"
    assert body["total"] == "76.50"


async def test_pedido_cnpj_guarda_snapshot_por_item_e_total(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    response = await cnpj_client.post(
        "/api/v1/orders",
        json={
            "items": [_item(_PRODUCT_A, 1), _item(_PRODUCT_B, 30)],
            "payment_method": "PIX",
        },
        headers={"Idempotency-Key": "cnpj-order-snapshot-0001"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "2185.00"
    assert body["list_subtotal"] == "3100.00"
    assert body["cnpj_discount_total"] == "915.00"
    assert body["total"] == "2185.00"
    items = {item["sku"]: item for item in body["items"]}
    assert items["CNPJ-A"]["list_unit_price"] == "100.00"
    assert items["CNPJ-A"]["list_line_total"] == "100.00"
    assert items["CNPJ-A"]["cnpj_discount_percent"] == "15.00"
    assert items["CNPJ-A"]["cnpj_discount_band"] == 15
    assert items["CNPJ-A"]["cnpj_discount_amount"] == "15.00"
    assert items["CNPJ-A"]["unit_price"] == "85.00"
    assert items["CNPJ-B"]["list_unit_price"] == "100.00"
    assert items["CNPJ-B"]["list_line_total"] == "3000.00"
    assert items["CNPJ-B"]["cnpj_discount_percent"] == "30.00"
    assert items["CNPJ-B"]["cnpj_discount_band"] == 30
    assert items["CNPJ-B"]["cnpj_discount_amount"] == "900.00"
    assert items["CNPJ-B"]["unit_price"] == "70.00"

    fetched = await cnpj_client.get(f"/api/v1/orders/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["subtotal"] == "2185.00"


async def test_pedido_cpf_nao_recebe_desconto(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    _, person_client = cnpj_api
    response = await person_client.post(
        "/api/v1/orders",
        json={
            "items": [_item(_PRODUCT_A, 30)],
            "payment_method": "PIX",
        },
        headers={"Idempotency-Key": "cpf-order-no-discount-0001"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "3000.00"
    assert body["list_subtotal"] == "3000.00"
    assert body["cnpj_discount_total"] == "0.00"
    item = body["items"][0]
    assert item["unit_price"] == "100.00"
    assert item["list_unit_price"] == "100.00"
    assert item["list_line_total"] == "3000.00"
    assert item["cnpj_discount_amount"] == "0.00"
    assert item["cnpj_discount_percent"] is None
    assert item["cnpj_discount_band"] is None


async def test_pedido_antigo_sem_snapshot_continua_legivel(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
    pg: PostgresInstance,
) -> None:
    cnpj_client, _ = cnpj_api
    order_id = uuid.uuid4()
    item_id = uuid.uuid4()
    conn = pg.connect_admin(autocommit=False)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, NULL)", (_CNPJ_COMPANY,))
        conn.execute(
            "INSERT INTO orders (id, company_id, buyer_user_id, subtotal, total) "
            "VALUES (%s, %s, %s, 100.00, 100.00)",
            (order_id, _CNPJ_COMPANY, _CNPJ_USER),
        )
        conn.execute(
            "INSERT INTO order_items (id, order_id, company_id, product_id, sku, "
            "product_name, quantity, unit_price, base_unit_price, tier_min_quantity, "
            "line_total) VALUES (%s, %s, %s, %s, 'LEGACY-1', 'Item Legado', "
            "1, 100.00, 100.00, 1, 100.00)",
            (item_id, order_id, _CNPJ_COMPANY, _PRODUCT_A),
        )
        conn.commit()
    finally:
        conn.close()

    response = await cnpj_client.get(f"/api/v1/orders/{order_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["subtotal"] == "100.00"
    assert body["cnpj_discount_total"] == "0.00"
    item = body["items"][0]
    assert item["unit_price"] == "100.00"
    assert item["line_total"] == "100.00"
    assert item["list_unit_price"] is None
    assert item["list_line_total"] is None
    assert item["cnpj_discount_percent"] is None
    assert item["cnpj_discount_band"] is None
    assert item["cnpj_discount_amount"] is None


async def test_pagamento_usa_total_final_do_servidor(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    order = await cnpj_client.post(
        "/api/v1/orders",
        json={
            "items": [_item(_PRODUCT_A, 1)],
            "payment_method": "PIX",
        },
        headers={"Idempotency-Key": "cnpj-payment-total-0001"},
    )
    assert order.status_code == 201
    assert order.json()["total"] == "85.00"

    payment = await cnpj_client.post(
        "/api/v1/payments",
        json={"order_id": order.json()["id"], "method": "PIX"},
        headers={"Idempotency-Key": "cnpj-payment-total-0001"},
    )
    assert payment.status_code == 201
    body = payment.json()
    assert body["amount"] == "80.75"
    assert body["discount_amount"] == "4.25"


async def test_payload_adulterado_e_recusado(
    cnpj_api: tuple[httpx.AsyncClient, httpx.AsyncClient],
) -> None:
    cnpj_client, _ = cnpj_api
    cart = await cnpj_client.post(
        "/api/v1/cart/items",
        json={"product_id": str(_PRODUCT_A), "quantity": 1, "unit_price": "1.00"},
    )
    assert cart.status_code == 422

    order = await cnpj_client.post(
        "/api/v1/orders",
        json={
            "items": [
                {
                    "product_id": str(_PRODUCT_A),
                    "quantity": 1,
                    "unit_price": "1.00",
                    "cnpj_discount_percent": "30",
                }
            ],
            "payment_method": "PIX",
        },
        headers={"Idempotency-Key": "cnpj-adulterated-0001"},
    )
    assert order.status_code == 422
