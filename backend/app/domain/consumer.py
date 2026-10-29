"""Vocabulario compartilhado de consumidor (shared kernel de dominio).

O genero e usado tanto pelo contexto de contas (validacao do cadastro) quanto
pelo mapeador ORM de identidade (perfil do consumidor). Fica em ``app.domain``
para nao criar dependencia entre bounded contexts.
"""

from __future__ import annotations

from enum import StrEnum


class Gender(StrEnum):
    """Genero informado pelo consumidor (opcional, com opcao de nao informar)."""

    FEMININO = "FEMININO"
    MASCULINO = "MASCULINO"
    NAO_BINARIO = "NAO_BINARIO"
    OUTRO = "OUTRO"
    PREFIRO_NAO_INFORMAR = "PREFIRO_NAO_INFORMAR"
