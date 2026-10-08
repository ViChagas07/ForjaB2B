"""Probes de readiness das dependencias essenciais (PostgreSQL, Redis).

Funcoes pequenas usadas pelo endpoint /health/ready. Cada probe devolve
True/False e nunca propaga excecao: indisponibilidade vira status "error".
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def ping_database(engine: AsyncEngine) -> bool:
    """SELECT 1 com a role de runtime (sujeita a RLS, como em producao)."""
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            value: object = result.scalar_one()
            return value == 1
    except Exception:  # noqa: BLE001 - probe de readiness nao propaga
        return False
