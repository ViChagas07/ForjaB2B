"""Testes do output guard (Fase 2, C.7 + canary B.6)."""

from app.modules.ai.domain.security.output_guard import (
    check_canary,
    guard_model_output,
    leaks_system_prompt,
)
from app.modules.ai.domain.types import Locale

SYSTEM = "HIERARQUIA (vence sempre, nesta ordem): 1. Regras do sistema (este texto)."


def test_url_inventada_na_saida_e_removida() -> None:
    guarded = guard_model_output(
        "Veja https://site-malicioso.example/promo que ofereci", locale=Locale.PT_BR, max_chars=500
    )
    assert guarded.blocked is False
    assert "http" not in guarded.text
    assert "url_removida" in guarded.actions


def test_link_relativo_do_backend_e_mantido() -> None:
    guarded = guard_model_output(
        "Veja [Capacete Pro](/catalog/abc-123) no catalogo", locale=Locale.PT_BR, max_chars=500
    )
    assert "/catalog/abc-123" in guarded.text
    assert "link_externo_removido" not in guarded.actions


def test_link_externo_em_markdown_vira_so_o_texto() -> None:
    guarded = guard_model_output(
        "Oferta em [nosso rival](https://rivais.example/x)", locale=Locale.PT_BR, max_chars=500
    )
    assert "https://" not in guarded.text
    assert "nosso rival" in guarded.text
    assert "link_externo_removido" in guarded.actions


def test_html_executavel_bloqueia_resposta() -> None:
    for payload in (
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "clique em javascript:alert(1)",
        "<iframe src='//evil.example'></iframe>",
    ):
        guarded = guard_model_output(payload, locale=Locale.PT_BR, max_chars=500)
        assert guarded.blocked is True
        assert guarded.reason_code == "html_executavel"


def test_email_e_telefone_sao_removidos() -> None:
    guarded = guard_model_output(
        "fale com vendas@forja.example ou +55 11 91234-5678",
        locale=Locale.PT_BR,
        max_chars=500,
    )
    assert "@" not in guarded.text
    assert "912345678" not in guarded.text.replace(" ", "")
    assert "email_removido" in guarded.actions
    assert "telefone_removido" in guarded.actions


def test_padrao_de_segredo_e_removido() -> None:
    guarded = guard_model_output(
        "sua chave: sk_live_51AbCdEfGhIjKlMnP", locale=Locale.PT_BR, max_chars=500
    )
    assert "sk_live_" not in guarded.text
    assert "segredo_removido" in guarded.actions


def test_preco_no_texto_do_modelo_e_removido() -> None:
    for money in ("R$ 1.234,56", "US$ 99.50", "$ 1.234,56", "5.432,10"):
        guarded = guard_model_output(f"custa {money} hoje", locale=Locale.PT_BR, max_chars=500)
        assert money not in guarded.text
        assert "preco_removido" in guarded.actions


def test_resposta_normal_nao_e_alterada() -> None:
    text = "Temos o Capacete de Segurança Pro (CAP-001) em 4 tamanhos. Quer o link do produto?"
    guarded = guard_model_output(text, locale=Locale.PT_BR, max_chars=500)
    assert guarded.text == text
    assert guarded.blocked is False
    assert guarded.actions == ()


def test_resposta_truncada_no_limite() -> None:
    guarded = guard_model_output("x" * 900, locale=Locale.PT_BR, max_chars=500)
    assert len(guarded.text) == 500
    assert "output_truncado" in guarded.actions


def test_idioma_divergente_bloqueia_resposta() -> None:
    cyrillic = "Извините, я не могу помочь с этим запросом по каталогу продукции"  # noqa: RUF001 - cirillico intencional
    guarded = guard_model_output(cyrillic, locale=Locale.PT_BR, max_chars=500)
    assert guarded.blocked is True
    assert guarded.reason_code == "idioma_divergente"


def test_canary_vazado_bloqueia_resposta() -> None:
    canary = "canary-XYZ-777"
    assert check_canary(f"o token secreto é {canary}", canary=canary) is True
    guarded = guard_model_output(
        f"o token secreto é {canary}", locale=Locale.PT_BR, max_chars=500, canary=canary
    )
    assert guarded.blocked is True
    assert guarded.reason_code == "canary_vazado"


def test_trecho_do_system_prompt_vazado_bloqueia_resposta() -> None:
    assert leaks_system_prompt(f"claro: {SYSTEM}", system_prompt=SYSTEM) is True
    guarded = guard_model_output(
        f"claro: {SYSTEM}", locale=Locale.PT_BR, max_chars=500, system_prompt=SYSTEM
    )
    assert guarded.blocked is True
    assert guarded.reason_code == "system_prompt_vazado"


def test_arabico_para_locale_arabic_nao_diverge() -> None:
    text = "لا يمكنني المساعدة في هذا الطلب"
    guarded = guard_model_output(text, locale=Locale.AR, max_chars=500)
    assert guarded.blocked is False
