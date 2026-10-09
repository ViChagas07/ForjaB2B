"""Regras de dominio de privacidade (pure Python, sem frameworks).

A exclusao de dados pessoais e uma ANONIMIZACAO: preserva a linha do usuario
(FKs, registros financeiros/fiscais/auditoria) mas remove os campos que
identificam a pessoa. O email anonimizado e deterministico e unico por usuario,
mantendo a unicidade do ``users.email`` sem expor o endereco original.
"""

from __future__ import annotations

import uuid

_ANONYMIZED_DOMAIN = "anonymized.forja.local"


def anonymized_email(user_id: uuid.UUID) -> str:
    """Email anonimizado deterministico (unico por usuario)."""
    return f"deleted+{user_id}@{_ANONYMIZED_DOMAIN}"


def anonymized_name() -> str:
    """Nome anonimizado para exibicao pos-exclusao."""
    return "Usuario Removido"
