"""Testes dos adaptadores LLM (fake scriptavel e fabrica OpenAI-compativel).

Nenhum teste chama rede ou LLM real: a fabrica e testada apenas na
CONSTRUCAO (sem requisicao) e com a fonte de dados sendo `Settings()`.
"""

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.modules.ai.application.ports import ResilientLLM
from app.modules.ai.infrastructure.llm_fake import FakeLLM
from app.modules.ai.infrastructure.llm_openai import LangChainOpenAILLM, build_langchain_llm

_MESSAGES: list[dict[str, str]] = [{"role": "user", "content": "oi"}]


class _Card(BaseModel):
    sku: str


async def test_fake_llm_devolve_roteiro_em_ordem() -> None:
    llm = FakeLLM(structured=[_Card(sku="CAP-001")], texts=["primeira", "segunda"])

    card = await llm.complete_structured(schema=_Card, messages=_MESSAGES)  # type: ignore[arg-type]
    text1 = await llm.complete_text(messages=_MESSAGES)  # type: ignore[arg-type]
    text2 = await llm.complete_text(messages=_MESSAGES)  # type: ignore[arg-type]

    assert card == _Card(sku="CAP-001")
    assert (text1, text2) == ("primeira", "segunda")
    assert llm.text_calls == [_MESSAGES, _MESSAGES]
    assert llm.structured_calls[0][0] is _Card


async def test_fake_llm_roteiro_esgotado_e_erro_de_teste() -> None:
    llm = FakeLLM()  # sem roteiro
    with pytest.raises(AssertionError):
        await llm.complete_text(messages=_MESSAGES)  # type: ignore[arg-type]


async def test_fake_llm_pode_ser_envelopado_pelo_resiliente() -> None:
    llm = FakeLLM(texts=["ok"])
    resilient = ResilientLLM(llm, timeout_seconds=1.0)  # type: ignore[arg-type]
    assert await resilient.complete_text(messages=_MESSAGES) == "ok"


def test_fabrica_rejeita_llm_nao_configurado() -> None:
    settings = Settings(_env_file=None)  # sem LLM_BASE_URL/LLM_API_KEY
    assert settings.llm_ready is False
    with pytest.raises(Exception, match="llm_not_configured"):
        build_langchain_llm(settings)


def test_adaptador_openai_compativel_constroi_sem_rede() -> None:
    # Construcao NAO dispara requisicao: apenas valida a configuracao.
    adapter = LangChainOpenAILLM(
        base_url="http://localhost:9/v1",
        api_key="test-key-not-real",
        model="fake-model",
        timeout_seconds=5.0,
        max_tokens=128,
    )
    assert adapter is not None
