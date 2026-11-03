"""Mensagem amigavel de degradacao do assistente (11 locales).

Usada quando o LLM local esta desligado, sem LM Studio ou falhou. Nunca
substitui a resposta neutra de seguranca (bloqueio/off-topic): e apenas o
aviso de "modo demonstracao", acompanhado dos cartoes deterministicos que o
backend conseguir montar. Texto puro, sem HTML/links.
"""

from __future__ import annotations

from app.modules.ai.domain.types import Locale

_DEMO_MODE: dict[str, str] = {
    "pt-BR": (
        "O assistente de IA está em modo demonstração local. "
        "Veja no README como rodar o modelo no LM Studio."
    ),
    "en": (
        "The AI assistant is in local demo mode. "
        "See the README for how to run the model with LM Studio."
    ),
    "es": (
        "El asistente de IA está en modo demostración local. "
        "Consulta el README para ejecutar el modelo con LM Studio."
    ),
    "ar": (
        "مساعد الذكاء الاصطناعي في وضع العرض المحلي. "
        "راجع README لمعرفة كيفية تشغيل النموذج في LM Studio."
    ),
    "de": (
        "Der KI-Assistent läuft im lokalen Demo-Modus. "
        "Im README steht, wie du das Modell mit LM Studio startest."
    ),
    "fr": (
        "L'assistant IA est en mode démonstration local. "
        "Consultez le README pour lancer le modèle avec LM Studio."
    ),
    "it": (
        "L'assistente IA è in modalità dimostrazione locale. "
        "Consulta il README per avviare il modello con LM Studio."
    ),
    "ja": (
        "AIアシスタントはローカルデモモードです。"
        "LM Studioでモデルを実行する方法はREADMEをご覧ください。"
    ),
    "ko": (
        "AI 어시스턴트가 로컬 데모 모드입니다. "
        "LM Studio에서 모델을 실행하는 방법은 README를 참고하세요."
    ),
    "ru": (
        "ИИ-ассистент работает в локальном демо-режиме. "
        "В README описано, как запустить модель в LM Studio."  # noqa: RUF001
    ),
    "zh-CN": "AI 助手当前处于本地演示模式。请参阅 README 了解如何使用 LM Studio 运行模型。",
}


def demo_mode_response(locale: Locale) -> str:
    """Aviso traduzido de modo demonstracao (fallback pt-BR)."""
    return _DEMO_MODE.get(locale.value, _DEMO_MODE["pt-BR"])
