"""Hash de senha Argon2id (argon2-cffi).

Argon2id e o algoritmo recomendado para senhas (resistente a GPU/ASIC e a
side-channels de cache). Nenhuma senha e logada nem devolvida; o hash
``$argon2id$...`` e a unica representacao persistida.

A verificacao contra um hash DUMMY quando a senha e ausente (usuario nao
encontrado) mantem o tempo de resposta aproximadamente constante, mitigando
enumeracao de usuarios por canal lateral de tempo.
"""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Hash Argon2id valido de uma senha descartavel, usado apenas para equalizar
# o tempo de verificacao quando o usuario nao existe (anti-enumeracao).
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "dW5tb3VudGFibGUtc2FsdC1mb3ItdGltaW5n$"
    "pZ2VhZF9zaXplZF9oYXNoX3ZhbHVlX2R1bW15X2RpZ2VzdF9zdHJpbmc"
)


class Argon2PasswordHasher:
    """Implementacao concreta da porta PasswordHasher (Argon2id)."""

    def __init__(self) -> None:
        self._hasher = _Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str | None) -> bool:
        candidate = password_hash if password_hash is not None else _DUMMY_HASH
        try:
            return self._hasher.verify(candidate, password)
        except (VerificationError, VerifyMismatchError, InvalidHashError):
            return False
