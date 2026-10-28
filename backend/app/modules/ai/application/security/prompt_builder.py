"""Construtor do prompt do chat (itens B.5/B.6): montagem em CODIGO.

- System prompt fixo e VERSIONADO em arquivo de dados
  (`data/system_prompt.chat.v1.txt`) com hierarquia explicita
  (sistema > usuario > dados) e canary token.
- TODO conteudo nao confiavel (mensagem do usuario, historico, nomes e
  descricoes de produto, itens de carrinho, resultado de ferramenta) entra
  DENTRO de blocos delimitados `<dados_nao_confiaveis id=TAG ...>` com tag
  ALEATORIA por requisicao, e e tratado como DADO, nunca instrucao.
- Ocorrencias dos proprios delimitadores sao REMOVIDAS do conteudo antes
  do encapsulamento (anti fuga do bloco).
- A tag aleatoria usa `secrets` por padrao; testes injetam `tag_factory`
  deterministica. NENHUM preco/PII entra no prompt (responsabilidade do
  chamador; o builder apenas encapsula como dado).
"""

from __future__ import annotations

import importlib.resources
import re
import secrets
from collections.abc import Callable, Sequence
from functools import lru_cache

from app.modules.ai.domain.types import Locale
from app.modules.ai.application.ports import LLMMessage

_SYSTEM_PROMPT_FILE = "system_prompt.chat.v1.txt"

# Variacoes possiveis do delimitador (tentativa de fuga), com e sem acento:
# remove qualquer ocorrencia de tags parecidas com <dados_nao_confiaveis ...>.
_DELIMITER_LIKE = re.compile(
    r"(?i)<\s*/?\s*dados[ _-]{0,2}n[ãa]o[ _-]{0,2}"
    r"confi[áa]v[ée]?[ií]?[lš]?[sš]?\b[^<>]{0,80}>"
)
_TAG_LABEL_SAFE = re.compile(r"^[a-z0-9_.:-]{1,40}$", re.IGNORECASE)


@lru_cache(maxsize=1)
def load_system_prompt_template() -> str:
    """System prompt versionado (com placeholders {locale} e {canary})."""
    resource = importlib.resources.files("app.modules.ai.application.security").joinpath(
        f"data/{_SYSTEM_PROMPT_FILE}"
    )
    return resource.read_text(encoding="utf-8")


def system_prompt_version() -> str:
    return _SYSTEM_PROMPT_FILE


def strip_delimiters(content: str) -> str:
    """Remove do conteudo nao confiavel qualquer ocorrencia dos delimitadores."""
    return _DELIMITER_LIKE.sub("", content)


class PromptBuilder:
    """Monta as mensagens do chat: sistema + dados nao confiaveis encapsulados."""

    def __init__(
        self,
        *,
        canary_token: str,
        tag_factory: Callable[[], str] | None = None,
        system_template: str | None = None,
    ) -> None:
        self._canary_token = canary_token
        self._tag_factory = tag_factory or (lambda: secrets.token_hex(8))
        self._system_template = system_template or load_system_prompt_template()

    def build(
        self,
        *,
        locale: Locale,
        user_message: str,
        history: Sequence[tuple[str, str]] = (),
        tool_context: str | None = None,
    ) -> list[LLMMessage]:
        """Mensagens finais: [system, ...historico como dado, ferramentas, usuario]."""
        tag = self._tag_factory()
        messages: list[LLMMessage] = [
            LLMMessage(
                role="system",
                content=self._system_template.format(
                    locale=locale.value, canary=self._canary_token
                ),
            )
        ]
        if history:
            turns = "\n".join(f"[{role}] {strip_delimiters(content)}" for role, content in history)
            messages.append(
                LLMMessage(role="user", content=untrusted_block("historico", turns, tag))
            )
        if tool_context:
            messages.append(
                LLMMessage(
                    role="user", content=untrusted_block("dados_do_catalogo", tool_context, tag)
                )
            )
        messages.append(
            LLMMessage(
                role="user", content=untrusted_block("mensagem_do_usuario", user_message, tag)
            )
        )
        return messages


def untrusted_block(label: str, content: str, tag: str) -> str:
    """Encapsula conteudo nao confiavel como DADO (delimitador com tag unica)."""
    if not _TAG_LABEL_SAFE.match(label):
        raise ValueError("label de bloco invalido")
    cleaned = strip_delimiters(content)
    return (
        f'<dados_nao_confiaveis id="{tag}" label="{label}">\n'
        f"{cleaned}\n"
        f'</dados_nao_confiaveis id="{tag}">'
    )
