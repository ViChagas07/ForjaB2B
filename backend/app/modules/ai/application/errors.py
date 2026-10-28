"""Erros tipados da camada de aplicacao de IA.

Contrato: qualquer falha de LLM (timeout, rede, resposta invalida) chega ao
chamador como `LLMUnavailableError` — um unico tipo para o fallback
deterministico (a falha de IA nunca bloqueia catalogo, carrinho, checkout
ou pedido). A mensagem NUNCA inclui texto do usuario, chave de API ou
conteudo de prompt/resposta.
"""

from __future__ import annotations


class LLMUnavailableError(RuntimeError):
    """LLM indisponivel ou falho apos esgotadas as tentativas."""


class AIDisabledError(RuntimeError):
    """IA desabilitada pelo kill switch (AI_AGENTS_ENABLED=false)."""


class ConversationAccessError(RuntimeError):
    """Acesso a conversa fora do escopo (visitante x dono x tenant)."""
