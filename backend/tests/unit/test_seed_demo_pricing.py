"""Testes unitarios dos dados de demonstracao da Fase 9A (precos e empresas).

Sem banco: valida que os precos de demonstracao estao em faixas plausiveis, que
os CNPJ sao sinteticos porem VALIDOS, e que as empresas/regras de preco sao
deterministicas e coerentes com a regra de precedencia.
"""

from __future__ import annotations

from decimal import Decimal

from app.infrastructure.db.seeds import (
    _DEMO_COMPANY_SPECS,
    _DEMO_PRODUCT_SPECS,
    _build_demo_tenants,
    _tenant_id,
)
from app.modules.companies.domain.cnpj import is_valid_cnpj

_RANGES_BY_CATEGORY: dict[str, tuple[Decimal, Decimal]] = {
    "protecao-cabeca": (Decimal("25"), Decimal("90")),
    "protecao-maos": (Decimal("5"), Decimal("60")),
    "protecao-visual": (Decimal("8"), Decimal("45")),
    "protecao-pes": (Decimal("70"), Decimal("220")),
    "protecao-auditiva": (Decimal("3"), Decimal("35")),
    "protecao-quedas": (Decimal("80"), Decimal("350")),
    "maquinas-estacionarias": (Decimal("600"), Decimal("9000")),
}


def test_precos_demo_dentro_das_faixas_por_categoria() -> None:
    for sku, name, category_slug, _brand, price, ca_mode, status, _uom in _DEMO_PRODUCT_SPECS:
        if status != "ACTIVE" or ca_mode in {"expired", "missing"}:
            continue  # nao vendavel: nao entra na regra de precos
        value = Decimal(price)
        if category_slug == "protecao-respiratoria":
            if "Semifacial" in name:
                low, high = Decimal("90"), Decimal("250")
            else:
                low, high = Decimal("3"), Decimal("15")
        elif category_slug in _RANGES_BY_CATEGORY:
            low, high = _RANGES_BY_CATEGORY[category_slug]
        else:
            continue  # ferramentas-eletricas: sem faixa fixa nesta fase
        assert low <= value <= high, f"{sku}: {value} fora da faixa [{low}, {high}]"


def test_cnpjs_demo_sao_sinteticos_e_validos() -> None:
    assert len(_DEMO_COMPANY_SPECS) == 3
    cnpjs = [spec[1] for spec in _DEMO_COMPANY_SPECS]
    assert len(set(cnpjs)) == 3, "CNPJ de demonstracao devem ser distintos"
    for _slug, cnpj, _legal, _trade in _DEMO_COMPANY_SPECS:
        assert is_valid_cnpj(cnpj), f"CNPJ {cnpj} deveria ser valido pelo algoritmo oficial"


def test_tenants_demo_sem_senha_nao_expoem_password_hash() -> None:
    tenants = _build_demo_tenants("pepper-de-teste", None)
    assert len(tenants) == 3
    for tenant in tenants:
        assert len(tenant.users) == 3
        assert {member["role"] for member in tenant.members} == {"ADMIN", "BUYER", "APPROVER"}
        assert all("password_hash" not in user for user in tenant.users)


def test_tenants_demo_com_senha_aplicam_hash() -> None:
    tenants = _build_demo_tenants("pepper-de-teste", "$argon2id$hash-ficticio")
    for tenant in tenants:
        assert all(user["password_hash"] == "$argon2id$hash-ficticio" for user in tenant.users)


def test_regras_por_empresa_seguem_condicoes_distintas() -> None:
    by_slug = {tenant.slug: tenant for tenant in _build_demo_tenants("pepper", None)}

    assert by_slug["metalurgica-alfa"].rules == []

    beta = by_slug["construcoes-beta"].rules
    assert [rule["rule_type"] for rule in beta] == ["PERCENT_DISCOUNT"]
    assert beta[0]["category_id"] is not None

    gama = by_slug["industria-gama"].rules
    assert sorted(str(rule["rule_type"]) for rule in gama) == [
        "FIXED_PRICE",
        "FIXED_PRICE",
        "PERCENT_DISCOUNT",
    ]
    fixed = [rule for rule in gama if rule["rule_type"] == "FIXED_PRICE"]
    assert all(rule["product_id"] is not None and rule["unit_price"] is not None for rule in fixed)


def test_ids_demo_sao_deterministicos() -> None:
    first = _build_demo_tenants("pepper", None)
    second = _build_demo_tenants("pepper", None)
    assert [tenant.id for tenant in first] == [tenant.id for tenant in second]
    assert [user["id"] for tenant in first for user in tenant.users] == [
        user["id"] for tenant in second for user in tenant.users
    ]


def test_tenant_id_deriva_do_namespace() -> None:
    assert _tenant_id("company", "metalurgica-alfa") == _tenant_id("company", "metalurgica-alfa")
    assert _tenant_id("company", "metalurgica-alfa") != _tenant_id("company", "construcoes-beta")
