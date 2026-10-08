"""Testes unitarios de senha (Argon2id) e politica de forca de senha."""

from __future__ import annotations

import pytest

from app.modules.identity.domain.errors import WeakPasswordError
from app.modules.identity.domain.rules import validate_password_strength
from app.modules.identity.infrastructure.password import Argon2PasswordHasher


def test_hash_usa_argon2id_e_nao_armazena_plaintext() -> None:
    hasher = Argon2PasswordHasher()
    digest = hasher.hash("Senha@Forte123")
    assert digest.startswith("$argon2id$")
    assert "Senha@Forte123" not in digest


def test_verify_senha_correta() -> None:
    hasher = Argon2PasswordHasher()
    digest = hasher.hash("Senha@Forte123")
    assert hasher.verify("Senha@Forte123", digest) is True


def test_verify_senha_incorreta() -> None:
    hasher = Argon2PasswordHasher()
    digest = hasher.hash("Senha@Forte123")
    assert hasher.verify("Senha@Errada999", digest) is False


def test_verify_hash_ausente_devolve_false() -> None:
    hasher = Argon2PasswordHasher()
    assert hasher.verify("qualquer", None) is False


def test_verify_hash_malformado_devolve_false() -> None:
    hasher = Argon2PasswordHasher()
    assert hasher.verify("qualquer", "nao-e-um-hash-argon2") is False


def test_hash_mesma_senha_gera_digests_distintos() -> None:
    hasher = Argon2PasswordHasher()
    first = hasher.hash("MesmaSenha123")
    second = hasher.hash("MesmaSenha123")
    assert first != second


def test_regra_senha_curta_levantada() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password_strength("curta")


def test_regra_senha_muito_longa_levantada() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password_strength("a" * 200)


def test_regra_senha_valida_passa() -> None:
    validate_password_strength("Senha@Forte123")
