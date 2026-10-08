"""Vocabulario de estado do modulo identity (pure Python, sem frameworks)."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    """Estados da conta de usuario, conforme o MEGA-PROMPT (secao 9)."""

    PENDING_EMAIL = "PENDING_EMAIL"  # aguardando verificacao de e-mail
    PENDING_APPROVAL = "PENDING_APPROVAL"  # aguardando aprovacao da empresa
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class MemberRole(StrEnum):
    """Papeis de um usuario dentro de uma empresa (team management)."""

    ADMIN = "ADMIN"  # administrador da empresa
    BUYER = "BUYER"  # comprador
    APPROVER = "APPROVER"  # aprovador (pedidos acima de limite)
    FINANCE = "FINANCE"  # financeiro


class MemberStatus(StrEnum):
    """Ciclo de vida do vinculo usuario x empresa."""

    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class IdentityProvider(StrEnum):
    """Provedores de identidade externa suportados (login social)."""

    GOOGLE = "google"
