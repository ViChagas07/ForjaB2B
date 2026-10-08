"""Testes do contrato de contexto tenant transacional (GUCs forja.*).

Cobre: roundtrip do setter, contexto ausente/invalido, current_user_id,
limpeza apos commit/rollback e nao vazamento de contexto na reutilizacao da
mesma conexao (cenario tipico de pool).
"""

from __future__ import annotations

import uuid

import psycopg

from .conftest import PostgresInstance

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _tx_conn(pg: PostgresInstance) -> psycopg.Connection:
    """Conexao de runtime em modo transacional (autocommit desligado)."""
    return pg.connect_app(autocommit=False)


def test_set_tenant_context_roundtrip_company_e_user(pg: PostgresInstance) -> None:
    conn = _tx_conn(pg)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
        row = conn.execute("SELECT app.current_company_id(), app.current_user_id()").fetchone()
        assert row == (TENANT_A, USER_A)
        conn.commit()
    finally:
        conn.close()


def test_contexto_ausente_retorna_null(pg: PostgresInstance) -> None:
    conn = _tx_conn(pg)
    try:
        row = conn.execute("SELECT app.current_company_id(), app.current_user_id()").fetchone()
        assert row == (None, None)
        conn.commit()
    finally:
        conn.close()


def test_contexto_invalido_retorna_null(pg: PostgresInstance) -> None:
    conn = _tx_conn(pg)
    try:
        conn.execute("SET LOCAL forja.current_company_id = 'nao-e-um-uuid'")
        row = conn.execute("SELECT app.current_company_id()").fetchone()
        assert row == (None,)
        conn.commit()
    finally:
        conn.close()


def test_setter_sem_usuario_limpa_current_user_id(pg: PostgresInstance) -> None:
    conn = _tx_conn(pg)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
        conn.execute("SELECT app.set_tenant_context(%s)", (TENANT_B,))
        row = conn.execute("SELECT app.current_company_id(), app.current_user_id()").fetchone()
        assert row == (TENANT_B, None)
        conn.commit()
    finally:
        conn.close()


def test_contexto_limpo_apos_commit_mesma_conexao(pg: PostgresInstance) -> None:
    conn = _tx_conn(pg)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
        conn.commit()

        row = conn.execute("SELECT app.current_company_id(), app.current_user_id()").fetchone()
        assert row == (None, None)
        conn.commit()
    finally:
        conn.close()


def test_contexto_limpo_apos_rollback_mesma_conexao(pg: PostgresInstance) -> None:
    conn = _tx_conn(pg)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
        conn.rollback()

        row = conn.execute("SELECT app.current_company_id(), app.current_user_id()").fetchone()
        assert row == (None, None)
        conn.commit()
    finally:
        conn.close()


def test_contexto_nao_vaza_entre_transacoes_tenants_diferentes(pg: PostgresInstance) -> None:
    """Reutilizacao da conexao (pool): tenant A nao contamina transacao de B."""
    conn = _tx_conn(pg)
    try:
        conn.execute("SELECT app.set_tenant_context(%s, %s)", (TENANT_A, USER_A))
        assert conn.execute("SELECT app.current_company_id()").fetchone() == (TENANT_A,)
        conn.commit()

        # Nova transacao na mesma conexao, sem definir contexto.
        assert conn.execute("SELECT app.current_company_id()").fetchone() == (None,)
        conn.commit()

        # Nova transacao definindo apenas tenant B: nada de A deve persistir.
        conn.execute("SELECT app.set_tenant_context(%s)", (TENANT_B,))
        row = conn.execute("SELECT app.current_company_id(), app.current_user_id()").fetchone()
        assert row == (TENANT_B, None)
        conn.commit()
    finally:
        conn.close()
