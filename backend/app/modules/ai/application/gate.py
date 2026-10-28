"""Kill switch dos agentes de IA (AI_AGENTS_ENABLED).

Unico ponto de decisao do kill switch: quando `ai_agents_enabled` e falso
(PADRAO), endpoints de IA respondem 503 com mensagem neutra e jobs de IA
nao fazem nada — e o comportamento do sistema fica identico ao de antes
(nenhuma chamada de LLM e feita, nenhum pacote de LLM e importado no
caminho de requisicao). Falha de IA nunca bloqueia catalogo, carrinho,
checkout ou pedido.
"""

from __future__ import annotations

from app.modules.ai.application.errors import AIDisabledError


def ensure_ai_enabled(*, enabled: bool) -> None:
    """Levanta `AIDisabledError` quando o kill switch esta desligado.

    Recebe o valor da flag por argumento (a camada de interface injeta
    `settings.ai_agents_enabled`); a application nao conhece Settings.
    """
    if not enabled:
        raise AIDisabledError("ai_disabled")
