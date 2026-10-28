"""Testes dos tipos puros do dominio de IA (Fase 12, passo 3)."""

import uuid

import pytest

from app.modules.ai.domain import AgentContext, GuardVerdict, Locale, ToolResult, resolve_locale


def test_resolve_locale_aceita_valores_exatos_case_insensitive() -> None:
    assert resolve_locale("pt-BR") is Locale.PT_BR
    assert resolve_locale("PT-br") is Locale.PT_BR
    assert resolve_locale("zh-cn") is Locale.ZH_CN


def test_resolve_locale_aceita_prefixo_idioma() -> None:
    assert resolve_locale("en-US") is Locale.EN
    assert resolve_locale("pt") is Locale.PT_BR


def test_resolve_locale_fallback_pt_br_para_desconhecido() -> None:
    assert resolve_locale("tlh") is Locale.PT_BR
    assert resolve_locale("") is Locale.PT_BR
    assert resolve_locale(None) is Locale.PT_BR


def test_agent_context_visitante_nao_autenticado() -> None:
    context = AgentContext(locale=resolve_locale("en"))
    assert context.user_id is None
    assert context.company_id is None
    assert context.is_authenticated is False


def test_agent_context_autenticado_vem_do_servidor() -> None:
    user_id, company_id = uuid.uuid4(), uuid.uuid4()
    context = AgentContext(
        locale=Locale.PT_BR, user_id=user_id, company_id=company_id, conversation_id=uuid.uuid4()
    )
    assert context.is_authenticated is True


def test_tool_result_e_valor_imutavel() -> None:
    result = ToolResult(name="product_cards", ok=True, data={"cards": []})
    with pytest.raises(Exception, match="cannot assign to field"):  # frozen dataclass
        result.name = "other"  # type: ignore[misc]


def test_guard_verdict_allow_e_block() -> None:
    assert GuardVerdict.allow().allowed is True
    blocked = GuardVerdict.block("prompt_injection")
    assert blocked.allowed is False
    assert blocked.reason_code == "prompt_injection"
