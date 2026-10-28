"""Testes do payload de auditoria de agentes (Fase 12, passo 6).

Regra de seguranca: o payload NUNCA carrega o texto completo do usuario —
so hash, tamanho e prefixo sanitizado de 80 caracteres.
"""

import hashlib

from app.modules.ai.domain import build_audit_payload, sanitize_prefix

_LONG_TEXT = ("palavra " * 40).strip()  # 280 chars


def test_payload_nunca_carrega_texto_completo() -> None:
    payload = build_audit_payload(_LONG_TEXT)
    serialized = str(payload)
    assert len(str(payload["text_prefix"])) == 80  # cortado no limite
    # A cauda do texto original (alem do prefixo) nao aparece no payload.
    assert _LONG_TEXT[-100:] not in serialized
    assert _LONG_TEXT[100:] not in serialized


def test_payload_hash_e_tamanho_do_texto_original() -> None:
    payload = build_audit_payload("oi")
    assert payload["text_chars"] == 2
    assert payload["text_sha256"] == hashlib.sha256(b"oi").hexdigest()


def test_prefixo_sanitiza_controles_e_colapsa_espacos() -> None:
    dirty = "a\r\nb\x00c\x1f\td   e"
    clean = sanitize_prefix(dirty)
    assert clean == "a b c d e"
    for ch in clean:
        assert ch.isprintable()


def test_prefixo_vazio_para_texto_de_controles() -> None:
    assert sanitize_prefix("\x00\x01\x02") == ""


def test_prefixo_de_texto_longo_corta_em_80() -> None:
    assert len(sanitize_prefix(_LONG_TEXT)) == 80
