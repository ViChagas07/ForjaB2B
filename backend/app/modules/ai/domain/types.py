"""Tipos puros do contexto de IA.

Dinheiro, identidade e conteudo NUNCA entram aqui a titulo de dado do LLM:
`AgentContext` carrega apenas o que o SERVIDOR conhece (autenticacao e
idioma); `ToolResult` carrega apenas o resultado de ferramentas internas
(dados montados pelo backend a partir do PostgreSQL); `GuardVerdict` e o
resultado de um guard de seguranca; `Locale` e o vocabulario de idiomas da
interface (11 locales do site).

Sem imports de framework (pydantic, fastapi, langchain, langgraph) por
contrato do import-linter.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class Locale(StrEnum):
    """Os 11 idiomas da interface do site (UI_LOCALES do Settings)."""

    PT_BR = "pt-BR"
    EN = "en"
    ZH_CN = "zh-CN"
    JA = "ja"
    KO = "ko"
    RU = "ru"
    ES = "es"
    DE = "de"
    FR = "fr"
    IT = "it"
    AR = "ar"


_DEFAULT_LOCALE = Locale.PT_BR


def resolve_locale(raw: str | None) -> Locale:
    """Normaliza uma string de idioma para o vocabulario do site.

    Aceita o valor exato (case-insensitive) ou o prefixo antes de ``-``
    (``pt`` -> ``pt-BR``). Desconhecido/nulo -> ``pt-BR`` (fallback do site).
    """
    if raw is None:
        return _DEFAULT_LOCALE
    candidate = raw.strip()
    if not candidate:
        return _DEFAULT_LOCALE
    lowered = candidate.lower()
    for member in Locale:
        if lowered == member.value.lower():
            return member
    prefix = lowered.split("-", 1)[0]
    for member in Locale:
        if prefix == member.value.lower().split("-", 1)[0]:
            return member
    return _DEFAULT_LOCALE


@dataclass(frozen=True, kw_only=True)
class AgentContext:
    """Contexto do chamador, definido SOMENTE pelo servidor.

    `user_id`/`company_id` vem do JWT (AuthContext) no servidor — nunca de
    argumento do LLM, do corpo da requisicao ou do historico. Visitante tem
    ambos ``None``; usuario logado tem ao menos `user_id`.
    """

    locale: Locale = _DEFAULT_LOCALE
    user_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None and self.company_id is not None


@dataclass(frozen=True, kw_only=True)
class ToolResult:
    """Resultado de uma ferramenta interna (dados montados pelo backend).

    `data` nunca contem PII nem segredos: e material de apresentacao (ex.:
    cartoes de produto com id/nome/imagem/link) calculado pelo codigo a
    partir do PostgreSQL. O LLM so o referencia, nunca o produz.
    """

    name: str
    ok: bool = True
    data: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class GuardVerdict:
    """Veredicto de um guard de seguranca/escopo sobre uma acao ou saida.

    `reason_code` e um codigo estavel (sem texto do usuario) para metricas e
    audit log; texto jamais vai no motivo.
    """

    allowed: bool
    reason_code: str | None = None

    @classmethod
    def allow(cls) -> GuardVerdict:
        return cls(allowed=True)

    @classmethod
    def block(cls, reason_code: str) -> GuardVerdict:
        return cls(allowed=False, reason_code=reason_code)
