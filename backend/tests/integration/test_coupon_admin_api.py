"""API administrativa de cupons: auth, validacoes, filtros, PATCH e DELETE."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import PostgresDsn

from app.core.config import Settings
from app.infrastructure.cache.redis import close_redis_client
from app.main import create_app
from app.modules.identity.infrastructure.password import Argon2PasswordHasher

from .conftest import PostgresInstance

_COMPANY = uuid.UUID("aaaa0000-0000-4000-8000-00000000a001")
_ADMIN = uuid.UUID("aaaa0000-0000-4000-8000-00000000a002")
_BUYER = uuid.UUID("aaaa0000-0000-4000-8000-00000000a003")
_MEMBER_ADMIN = uuid.UUID("aaaa0000-0000-4000-8000-00000000a004")
_MEMBER_BUYER = uuid.UUID("aaaa0000-0000-4000-8000-00000000a005")
_ADMIN_EMAIL = "coupon-admin@test.local"
_BUYER_EMAIL = "coupon-buyer@test.local"
_PASSWORD = "Senha@Forte123"
_CNPJ = "88777666000155"


def _cpf_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _set_tenant(conn: object) -> None:
    conn.execute("SELECT app.set_tenant_context(%s, %s)", (_COMPANY, _ADMIN))


def _seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash(_PASSWORD)
    conn = pg.connect_admin(autocommit=False)
    try:
        _set_tenant(conn)
        conn.execute(
            "INSERT INTO companies (id, cnpj, legal_name, status) "
            "VALUES (%s, %s, 'Cupom Admin Empresa', 'ACTIVE') ON CONFLICT DO NOTHING",
            (_COMPANY, _CNPJ),
        )
        for user_id, email, full_name in (
            (_ADMIN, _ADMIN_EMAIL, "Cupom Admin"),
            (_BUYER, _BUYER_EMAIL, "Cupom Buyer"),
        ):
            conn.execute(
                "INSERT INTO users (id, company_id, email, full_name, cpf_hash, "
                "password_hash, status) VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE') "
                "ON CONFLICT DO NOTHING",
                (user_id, _COMPANY, email, full_name, _cpf_hash(email), password_hash),
            )
        conn.execute(
            "INSERT INTO company_members (id, company_id, user_id, role, status) "
            "VALUES (%s, %s, %s, 'ADMIN', 'ACTIVE'), (%s, %s, %s, 'BUYER', 'ACTIVE') "
            "ON CONFLICT DO NOTHING",
            (_MEMBER_ADMIN, _COMPANY, _ADMIN, _MEMBER_BUYER, _COMPANY, _BUYER),
        )
        conn.commit()
    finally:
        conn.close()


def _cleanup(pg: PostgresInstance) -> None:
    conn = pg.connect_admin(autocommit=False)
    try:
        _set_tenant(conn)
        conn.execute(
            "DELETE FROM coupon_redemptions WHERE coupon_id IN "
            "(SELECT id FROM coupons WHERE created_by = %s)",
            (_ADMIN,),
        )
        conn.execute("DELETE FROM orders WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM coupons WHERE created_by = %s", (_ADMIN,))
        conn.execute("DELETE FROM audit_log WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM company_members WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM users WHERE company_id = %s", (_COMPANY,))
        conn.execute("DELETE FROM companies WHERE id = %s", (_COMPANY,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def coupon_seed(pg: PostgresInstance, migrated_domain_schema: None) -> None:
    _seed(pg, migrated_domain_schema)


@pytest.fixture()
async def coupon_client(
    test_settings: Settings,
    admin_database_url: str,
    coupon_seed: None,
    pg: PostgresInstance,
) -> AsyncIterator[httpx.AsyncClient]:
    settings = test_settings.model_copy(
        update={"database_admin_url": PostgresDsn(admin_database_url)}
    )
    app = create_app(settings)
    if app.state.redis_client is not None:
        async for bucket_key in app.state.redis_client.scan_iter("rl:*"):
            await app.state.redis_client.delete(bucket_key)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": _ADMIN_EMAIL, "password": _PASSWORD},
            )
            assert login.status_code == 200
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            yield client
    finally:
        await app.state.db_engine.dispose()
        if app.state.admin_engine is not None:
            await app.state.admin_engine.dispose()
        await close_redis_client(app.state.redis_client)
        _cleanup(pg)


def _payload(
    *,
    code: str = "CUPOM10",
    percent: str = "10.00",
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": code,
        "type": "PRODUCT_TOTAL",
        "percent": percent,
    }
    payload.update(extra)
    return payload


async def _login_buyer(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": _BUYER_EMAIL, "password": _PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_sem_token_401(coupon_client: httpx.AsyncClient) -> None:
    response = await coupon_client.get("/api/v1/admin/coupons", headers={"Authorization": ""})
    assert response.status_code == 401


async def test_buyer_recebe_403(coupon_client: httpx.AsyncClient) -> None:
    headers = await _login_buyer(coupon_client)
    response = await coupon_client.get("/api/v1/admin/coupons", headers=headers)
    assert response.status_code == 403


async def test_buyer_nao_altera_cupom_nem_usa_metodo_alternativo(
    coupon_client: httpx.AsyncClient,
) -> None:
    created = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="AUTH-TEST"))
    assert created.status_code == 201
    coupon_id = created.json()["id"]
    headers = await _login_buyer(coupon_client)

    assert (
        await coupon_client.get(f"/api/v1/admin/coupons/{coupon_id}", headers=headers)
    ).status_code == 403
    assert (
        await coupon_client.patch(
            f"/api/v1/admin/coupons/{coupon_id}",
            headers=headers,
            json={"percent": "99.00"},
        )
    ).status_code == 403
    assert (
        await coupon_client.delete(f"/api/v1/admin/coupons/{coupon_id}", headers=headers)
    ).status_code == 403
    assert (
        await coupon_client.post("/api/v1/admin/coupons/generate-code", headers=headers)
    ).status_code == 403
    assert (
        await coupon_client.put(
            f"/api/v1/admin/coupons/{coupon_id}",
            json={"percent": "99.00"},
        )
    ).status_code == 405


async def test_criar_normaliza_codigo_e_audita(
    coupon_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    response = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="  cupom10  "))
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "CUPOM10"
    assert body["total_uses"] == 0
    assert body["total_discounted"] == "0.00"

    conn = pg.connect_admin(autocommit=False)
    try:
        _set_tenant(conn)
        row = conn.execute(
            "SELECT action FROM audit_log WHERE resource_id = %s AND company_id = %s",
            (uuid.UUID(body["id"]), _COMPANY),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    assert row is not None and row[0] == "coupon.created"


async def test_criar_duplicado_409(coupon_client: httpx.AsyncClient) -> None:
    assert (await coupon_client.post("/api/v1/admin/coupons", json=_payload())).status_code == 201
    duplicate = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="cupom10"))
    assert duplicate.status_code == 409
    assert "já existe" in duplicate.json()["detail"]


@pytest.mark.parametrize("percent", ["0", "100.01"])
async def test_criar_percentual_invalido_422(
    coupon_client: httpx.AsyncClient, percent: str
) -> None:
    response = await coupon_client.post("/api/v1/admin/coupons", json=_payload(percent=percent))
    assert response.status_code == 422


async def test_criar_validade_invalida_422(coupon_client: httpx.AsyncClient) -> None:
    now = datetime.now(UTC)
    response = await coupon_client.post(
        "/api/v1/admin/coupons",
        json=_payload(
            valid_from=now.isoformat(),
            valid_until=(now - timedelta(seconds=1)).isoformat(),
        ),
    )
    assert response.status_code == 422
    assert "validade final" in response.json()["detail"]


async def test_criar_codigo_automatico(coupon_client: httpx.AsyncClient) -> None:
    response = await coupon_client.post(
        "/api/v1/admin/coupons",
        json={"type": "SHIPPING", "percent": "50.00"},
    )
    assert response.status_code == 201
    assert re.fullmatch(r"FORJA-[A-Z0-9]{6}", response.json()["code"])


async def test_gerar_codigo_endpoint(coupon_client: httpx.AsyncClient) -> None:
    response = await coupon_client.post("/api/v1/admin/coupons/generate-code")
    assert response.status_code == 200
    assert re.fullmatch(r"FORJA-[A-Z0-9]{6}", response.json()["code"])


async def test_payload_com_campo_extra_422(coupon_client: httpx.AsyncClient) -> None:
    response = await coupon_client.post("/api/v1/admin/coupons", json=_payload(desconto_topo="10"))
    assert response.status_code == 422


async def test_restricao_para_empresa_inexistente_422(
    coupon_client: httpx.AsyncClient,
) -> None:
    response = await coupon_client.post(
        "/api/v1/admin/coupons",
        json=_payload(restricted_company_id=str(uuid.uuid4())),
    )
    assert response.status_code == 422
    assert "Empresa restrita" in response.json()["detail"]


def _insert_redemption(
    pg: PostgresInstance, *, coupon_id: uuid.UUID, amount: str = "10.00"
) -> uuid.UUID:
    order_id = uuid.uuid4()
    conn = pg.connect_admin(autocommit=False)
    try:
        _set_tenant(conn)
        conn.execute(
            "INSERT INTO orders (id, company_id, buyer_user_id, subtotal, total) "
            "VALUES (%s, %s, %s, 100.00, 100.00)",
            (order_id, _COMPANY, _ADMIN),
        )
        conn.execute(
            "INSERT INTO coupon_redemptions "
            "(coupon_id, order_id, company_id, amount_discounted) "
            "VALUES (%s, %s, %s, %s)",
            (coupon_id, order_id, _COMPANY, amount),
        )
        conn.commit()
    finally:
        conn.close()
    return order_id


async def test_listar_filtros_paginacao_e_usos(
    coupon_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    active = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-ATIVO"))
    assert active.status_code == 201
    now = datetime.now(UTC)
    expired = await coupon_client.post(
        "/api/v1/admin/coupons",
        json=_payload(
            code="CUPOM-EXPIRADO",
            valid_until=(now - timedelta(days=1)).isoformat(),
        ),
    )
    assert expired.status_code == 201
    exhausted = await coupon_client.post(
        "/api/v1/admin/coupons",
        json=_payload(code="CUPOM-ESGOTADO", usage_limit_total=1),
    )
    assert exhausted.status_code == 201
    order_id = _insert_redemption(pg, coupon_id=uuid.UUID(exhausted.json()["id"]))

    response = await coupon_client.get("/api/v1/admin/coupons")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    by_code = {item["code"]: item for item in body["items"]}
    assert by_code["CUPOM-ESGOTADO"]["total_uses"] == 1
    assert by_code["CUPOM-ESGOTADO"]["total_discounted"] == "10.00"

    active_list = await coupon_client.get("/api/v1/admin/coupons", params={"status": "ACTIVE"})
    assert [item["code"] for item in active_list.json()["items"]] == ["CUPOM-ATIVO"]

    expired_list = await coupon_client.get("/api/v1/admin/coupons", params={"status": "EXPIRED"})
    assert [item["code"] for item in expired_list.json()["items"]] == ["CUPOM-EXPIRADO"]

    exhausted_list = await coupon_client.get(
        "/api/v1/admin/coupons", params={"status": "EXHAUSTED"}
    )
    assert [item["code"] for item in exhausted_list.json()["items"]] == ["CUPOM-ESGOTADO"]

    search = await coupon_client.get("/api/v1/admin/coupons", params={"q": "cupom-ativo"})
    assert [item["code"] for item in search.json()["items"]] == ["CUPOM-ATIVO"]

    paged = await coupon_client.get("/api/v1/admin/coupons", params={"page": 1, "page_size": 1})
    assert paged.json()["total"] == 3
    assert len(paged.json()["items"]) == 1
    assert paged.json()["pages"] == 3
    assert order_id  # ordem inserida para o resgate


async def test_detalhe_com_ultimos_resgates(
    coupon_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    created = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-DETALHE"))
    coupon_id = uuid.UUID(created.json()["id"])
    order_id = _insert_redemption(pg, coupon_id=coupon_id)

    response = await coupon_client.get(f"/api/v1/admin/coupons/{coupon_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total_uses"] == 1
    assert body["total_discounted"] == "10.00"
    assert len(body["last_redemptions"]) == 1
    assert body["last_redemptions"][0]["order_id"] == str(order_id)
    assert body["last_redemptions"][0]["status"] == "APPLIED"


async def test_patch_com_resgate_bloqueia_codigo_e_tipo(
    coupon_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    created = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-PATCH"))
    coupon_id = uuid.UUID(created.json()["id"])
    _insert_redemption(pg, coupon_id=coupon_id)

    code_response = await coupon_client.patch(
        f"/api/v1/admin/coupons/{coupon_id}", json={"code": "OUTRO-CODIGO"}
    )
    assert code_response.status_code == 409
    assert "código" in code_response.json()["detail"]

    type_response = await coupon_client.patch(
        f"/api/v1/admin/coupons/{coupon_id}", json={"type": "SHIPPING"}
    )
    assert type_response.status_code == 409
    assert "tipo" in type_response.json()["detail"]

    allowed = await coupon_client.patch(
        f"/api/v1/admin/coupons/{coupon_id}",
        json={"percent": "25.00", "is_active": False},
    )
    assert allowed.status_code == 200
    assert allowed.json()["percent"] == "25.00"
    assert allowed.json()["is_active"] is False


async def test_patch_codigo_sem_resgate_permitido(
    coupon_client: httpx.AsyncClient,
) -> None:
    created = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-ANTIGO"))
    coupon_id = created.json()["id"]
    response = await coupon_client.patch(
        f"/api/v1/admin/coupons/{coupon_id}", json={"code": "  cupom-novo  "}
    )
    assert response.status_code == 200
    assert response.json()["code"] == "CUPOM-NOVO"


async def test_patch_codigo_duplicado_409(coupon_client: httpx.AsyncClient) -> None:
    first = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-A"))
    assert (
        await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-B"))
    ).status_code == 201
    response = await coupon_client.patch(
        f"/api/v1/admin/coupons/{first.json()['id']}", json={"code": "CUPOM-B"}
    )
    assert response.status_code == 409


async def test_patch_validade_invalida_422(coupon_client: httpx.AsyncClient) -> None:
    created = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-DATA"))
    now = datetime.now(UTC)
    response = await coupon_client.patch(
        f"/api/v1/admin/coupons/{created.json()['id']}",
        json={
            "valid_from": now.isoformat(),
            "valid_until": now.isoformat(),
        },
    )
    assert response.status_code == 422


async def test_delete_sem_resgate_204_e_404(coupon_client: httpx.AsyncClient) -> None:
    created = await coupon_client.post("/api/v1/admin/coupons", json=_payload(code="CUPOM-DELETE"))
    coupon_id = created.json()["id"]
    response = await coupon_client.delete(f"/api/v1/admin/coupons/{coupon_id}")
    assert response.status_code == 204
    assert (await coupon_client.get(f"/api/v1/admin/coupons/{coupon_id}")).status_code == 404


async def test_delete_com_resgate_409_e_sugere_desativar(
    coupon_client: httpx.AsyncClient, pg: PostgresInstance
) -> None:
    created = await coupon_client.post(
        "/api/v1/admin/coupons", json=_payload(code="CUPOM-COM-RESGATE")
    )
    coupon_id = uuid.UUID(created.json()["id"])
    _insert_redemption(pg, coupon_id=coupon_id)

    response = await coupon_client.delete(f"/api/v1/admin/coupons/{coupon_id}")
    assert response.status_code == 409
    assert "desative" in response.json()["detail"]
    assert (await coupon_client.get(f"/api/v1/admin/coupons/{coupon_id}")).status_code == 200
