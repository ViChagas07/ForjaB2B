"""Testes do kill switch e das metricas de IA (Fase 12, passo 7)."""

import pytest

from app.core.config import Settings
from app.core.metrics import (
    ai_guard_blocks_total,
    increment_ai_guard_block,
    llm_calls_total,
    llm_errors_total,
    llm_tokens_estimated_total,
    observe_llm_call,
)
from app.modules.ai.application.errors import AIDisabledError
from app.modules.ai.application.gate import ensure_ai_enabled


def test_kill_switch_default_e_desligado() -> None:
    settings = Settings(_env_file=None)
    assert settings.ai_agents_enabled is False


def test_ensure_ai_enabled_desligado_leva_erro_tipado() -> None:
    with pytest.raises(AIDisabledError):
        ensure_ai_enabled(enabled=False)


def test_ensure_ai_enabled_ligado_nao_faz_nada() -> None:
    assert ensure_ai_enabled(enabled=True) is None


def test_observe_llm_call_contabiliza_latencia_e_tokens() -> None:
    before = llm_calls_total.labels(agent="chat")._value.get()
    tokens_before = llm_tokens_estimated_total.labels(agent="chat")._value.get()
    observe_llm_call(agent="chat", duration=0.5, outcome="ok", estimated_tokens=42)
    assert llm_calls_total.labels(agent="chat")._value.get() == before + 1
    assert llm_tokens_estimated_total.labels(agent="chat")._value.get() == tokens_before + 42


def test_observe_llm_call_outcome_error_incrementa_erros() -> None:
    before = llm_errors_total.labels(agent="cart")._value.get()
    observe_llm_call(agent="cart", duration=0.1, outcome="error")
    assert llm_errors_total.labels(agent="cart")._value.get() == before + 1


def test_increment_ai_guard_block_incrementa() -> None:
    before = ai_guard_blocks_total.labels(agent="chat")._value.get()
    increment_ai_guard_block(agent="chat")
    assert ai_guard_blocks_total.labels(agent="chat")._value.get() == before + 1
