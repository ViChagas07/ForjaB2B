"""Testes da memoria de conversa (Fase 2, E.10)."""

from datetime import UTC, datetime, timedelta

from app.modules.ai.application.security.memory import (
    InMemoryConversationMemoryStore,
    MemoryTurn,
    SanitizedConversationMemory,
)


def make_memory(*, ttl_days: int = 30, max_turns: int = 10):
    clock = {"now": datetime(2026, 10, 28, 12, 0, tzinfo=UTC)}
    store = InMemoryConversationMemoryStore(ttl_days=ttl_days, clock=lambda: clock["now"])
    memory = SanitizedConversationMemory(store, max_turns=max_turns)
    return memory, clock


def test_memoria_so_tem_portas_para_conteudo_aprovado() -> None:
    _memory, _clock = make_memory()
    # Nao existe metodo para saida de ferramenta/produto/system prompt.
    methods = set(dir(SanitizedConversationMemory))
    assert "remember_user" in methods
    assert "remember_assistant" in methods
    forbidden = [method for method in methods if "tool" in method or "product" in method]
    assert forbidden == []


def test_memoria_renormaliza_ao_guardar() -> None:
    memory, _clock = make_memory()
    memory.remember_user("conv-1", sanitized_text="comprar  capacete\u200b com CA")
    window = memory.window("conv-1")
    assert window[0][1] == "comprar capacete com CA"


def test_janela_trunca_no_historico_configurado() -> None:
    memory, clock = make_memory(max_turns=10)
    base = datetime.now(UTC)
    for index in range(15):
        clock["now"] = base + timedelta(minutes=index)
        memory.remember_user("conv-1", sanitized_text=f"mensagem {index}", now=clock["now"])
    window = memory.window("conv-1")
    assert len(window) == 10
    assert window[-1][1] == "mensagem 14"
    assert window[0][1] == "mensagem 5"


def test_memoria_isolada_por_conversa() -> None:
    memory, _clock = make_memory()
    memory.remember_user("conv-A", sanitized_text="pergunta da empresa A")
    memory.remember_assistant("conv-B", approved_text="resposta da empresa B")
    assert memory.window("conv-A") == (("user", "pergunta da empresa A"),)
    assert memory.window("conv-B") == (("assistant", "resposta da empresa B"),)


def test_memoria_expira_por_ttl() -> None:
    memory, clock = make_memory(ttl_days=30)
    day0 = datetime(2026, 10, 1, tzinfo=UTC)
    clock["now"] = day0
    memory.remember_user("conv-1", sanitized_text="antiga", now=day0)
    clock["now"] = day0 + timedelta(days=31)
    assert memory.window("conv-1") == ()
    clock["now"] = day0 + timedelta(days=10)
    memory.remember_user("conv-1", sanitized_text="renova", now=clock["now"])
    clock["now"] = day0 + timedelta(days=39)  # 29 dias apos a atividade
    assert len(memory.window("conv-1")) == 1


def test_turno_guarda_apenas_role_conteudo_e_tempo() -> None:
    turn = MemoryTurn(role="user", content="oi", at=datetime.now(UTC))
    assert set(turn.__dataclass_fields__) == {"role", "content", "at"}
