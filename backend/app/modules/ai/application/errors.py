"""Erros tipados da camada de aplicacao de IA.

Contrato: qualquer falha de LLM (timeout, rede, resposta invalida) chega ao
chamador como `LLMUnavailableError` — um unico tipo para o fallback
deterministico (a falha de IA nunca bloqueia catalogo, carrinho, checkout
ou pedido). A mensagem NUNCA inclui texto do usuario, chave de API ou
conteudo de prompt/resposta.
"""

from __future__ import annotations


class LLMUnavailableError(RuntimeError):
    """LLM indisponivel ou falho apos esgotadas as tentativas.

    `kind` e um codigo estavel para log/telemetria (connection_refused,
    timeout, http_4xx, http_5xx, empty_response, reasoning_only, invalid_json,
    schema_mismatch, queue_full). Nunca contem prompt/resposta.
    """

    def __init__(self, message: str, *, kind: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind or message


class LLMQueueFullError(LLMUnavailableError):
    """Fila curta da GPU cheia: falha rapido e deixa o chamador degradar."""


class AIDisabledError(RuntimeError):
    """IA desabilitada pelo kill switch (AI_AGENTS_ENABLED=false)."""


class ConversationAccessError(RuntimeError):
    """Acesso a conversa fora do escopo (visitante x dono x tenant)."""
