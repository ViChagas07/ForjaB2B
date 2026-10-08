"""Vocabulario de estado do modulo privacy (pure Python, sem frameworks)."""

from __future__ import annotations

from enum import StrEnum


class ConsentPurpose(StrEnum):
    """Finalidade de um registro de consentimento (LGPD)."""

    TERMS = "TERMS"  # termos de uso
    PRIVACY = "PRIVACY"  # politica de privacidade
    MARKETING_EMAIL = "MARKETING_EMAIL"
    MARKETING_SMS = "MARKETING_SMS"
    MARKETING_WHATSAPP = "MARKETING_WHATSAPP"


class ConsentAction(StrEnum):
    """Acao registrada na trilha historica de consentimento."""

    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
