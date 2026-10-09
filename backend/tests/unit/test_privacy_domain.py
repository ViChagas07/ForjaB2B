"""Testes unitarios do dominio de privacidade (anonimizacao)."""

from __future__ import annotations

import uuid

from app.modules.privacy.domain.privacy import anonymized_email, anonymized_name

_USER_ID = uuid.UUID("cccc0000-0000-4000-8000-000000000001")


def test_email_anonimizado_deterministico_e_unico() -> None:
    email = anonymized_email(_USER_ID)
    assert email == f"deleted+{_USER_ID}@anonymized.forja.local"
    assert email == anonymized_email(_USER_ID)


def test_nome_anonimizado() -> None:
    assert anonymized_name() == "Usuario Removido"
