"""Hash de CPF (HMAC-SHA256 com pepper) para unicidade "um CPF, uma conta".

Mesmo esquema do seed da Fase 1: o CPF nunca e armazenado em texto claro, apenas
o hash deterministico. O pepper vem da configuracao (Settings.pepper) e nunca e
logado nem exposto.
"""

from __future__ import annotations

import hashlib
import hmac


class HmacCpfHasher:
    """Implementacao da porta CpfHasher (HMAC-SHA256)."""

    def __init__(self, pepper: str) -> None:
        self._pepper = pepper

    def hash(self, cpf: str) -> str:
        return hmac.new(
            self._pepper.encode("utf-8"), cpf.encode("utf-8"), hashlib.sha256
        ).hexdigest()
