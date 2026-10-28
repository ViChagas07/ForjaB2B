"""Gate de entrada: antijailbreak em TODA mensagem e na janela do historico.

Itens A.1/A.2/A.3: normaliza a mensagem, escaneia (a) a mensagem corrente,
(b) cada mensagem da janela recente e (c) a JUNCAO da janela + corrente
(ataque em multiplos turnos). Veredito BLOCK conta no contador por conversa;
ao atingir `max_blocks` (3), a conversa e ENCERRADA (outcome CLOSE) com a
mesma resposta neutra — o chamador registra no agent_audit_log.

A resposta de bloqueio/encerramento e a unica resposta neutra traduzida nos
11 locales (nunca explica regras nem revela o que foi detectado). Sem I/O:
a mensagem recente chega JA sanitizada (memoria so guarda conteudo aprovado).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.modules.ai.application.security.ports import BlockCounter
from app.modules.ai.domain.security.injection import (
    InjectionVerdict,
    VerdictLevel,
    neutral_response,
    scan_injection,
)
from app.modules.ai.domain.security.normalize import normalize_user_text
from app.modules.ai.domain.types import Locale


class InputOutcome(StrEnum):
    """Desfecho possivel de uma mensagem de entrada."""

    ALLOW = "ALLOW"
    SANITIZE = "SANITIZE"
    BLOCK = "BLOCK"
    CLOSE = "CLOSE"  # conversa encerrada por bloqueios repetidos


@dataclass(frozen=True, kw_only=True)
class InputDecision:
    """Decisao do gate: o que fazer com a mensagem corrente."""

    outcome: InputOutcome
    text: str | None = None  # texto normalizado (ALLOW/SANITIZE)
    reason_code: str | None = None  # codigo estavel para audit/metricas
    response: str | None = None  # resposta neutra localizada (BLOCK/CLOSE)


class InputGate:
    """Pipeline de entrada deterministico (nunca depende do LLM)."""

    def __init__(
        self,
        *,
        max_message_chars: int,
        window_turns: int,
        max_blocks: int = 3,
        block_counter: BlockCounter,
    ) -> None:
        self._max_message_chars = max_message_chars
        self._window_turns = window_turns
        self._max_blocks = max_blocks
        self._block_counter = block_counter

    def check(
        self,
        *,
        conversation_id: uuid.UUID,
        locale: Locale,
        raw_message: str,
        recent_user_messages: Sequence[str] = (),
    ) -> InputDecision:
        normalized = normalize_user_text(raw_message, max_chars=self._max_message_chars)

        window = [
            normalize_user_text(message, max_chars=self._max_message_chars).text
            for message in list(recent_user_messages)[-self._window_turns :]
        ]
        texts = [*window, normalized.text]
        current = scan_injection(normalized.text)
        window_verdicts = [scan_injection(message) for message in window]
        # Pares consecutivos (incluindo corrente + ultima da janela): pega
        # frases quebradas entre turnos ("ignore" + "as instruções anteriores").
        pair_verdicts = [
            scan_injection(f"{texts[index]} {texts[index + 1]}") for index in range(len(texts) - 1)
        ]
        combined = scan_injection(" ".join(texts))

        block = self._first_block((current, combined, *pair_verdicts, *window_verdicts))
        if block is not None:
            return self._block_decision(conversation_id, locale, block)

        sanitize_reasons = list(normalized.encoding_flags)
        if normalized.truncated:
            sanitize_reasons.append("message_truncated")
        if current.level == VerdictLevel.SANITIZE:
            sanitize_reasons.append(current.reason_code or "sanitize_unknown")
        if sanitize_reasons:
            return InputDecision(
                outcome=InputOutcome.SANITIZE,
                text=normalized.text,
                reason_code=sanitize_reasons[0],
            )
        return InputDecision(outcome=InputOutcome.ALLOW, text=normalized.text)

    def _first_block(self, verdicts: Sequence[InjectionVerdict]) -> InjectionVerdict | None:
        for verdict in verdicts:
            if verdict.level == VerdictLevel.BLOCK:
                return verdict
        return None

    def _block_decision(
        self, conversation_id: uuid.UUID, locale: Locale, verdict: InjectionVerdict
    ) -> InputDecision:
        blocks = self._block_counter.register_block(conversation_id)
        outcome = InputOutcome.CLOSE if blocks >= self._max_blocks else InputOutcome.BLOCK
        return InputDecision(
            outcome=outcome,
            reason_code=verdict.reason_code,
            response=neutral_response(locale),
        )
