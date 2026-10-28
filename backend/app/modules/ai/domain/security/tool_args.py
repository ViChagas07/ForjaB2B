"""Scanner de argumentos de ferramenta (itens D.8/D.9 — dominio puro).

- `IDENTITY_KEYS`: chaves de identidade que NUNCA podem vir do modelo —
  sao REMOVIDAS de qualquer argumento e injetadas pelo servidor
  (company_id/user_id vem da autenticacao, jamais do LLM).
- `scan_tool_arguments`: rejeita valores que parecam instrucao, SQL, URL
  ou caminho de arquivo (ferramentas do chat sao SOMENTE LEITURA e recebem
  identificadores, nunca conteudo livre do modelo).

Funcoes puras: sem I/O, sem framework.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.modules.ai.domain.security.injection import InjectionVerdict, VerdictLevel, scan_injection

# Chaves que so o servidor define; nunca aceitas do modelo (removidas sempre).
IDENTITY_KEYS = frozenset(
    {"company_id", "user_id", "tenant_id", "tenant", "company", "auth", "authorization", "token"}
)

_SQL_PATTERN = re.compile(
    r"(?i)\b(select|insert|update|delete|drop|alter|truncate|grant|revoke|exec|waitfor)\b|--|/\*|\bor\s+1\s*=\s*1\b"
)
_URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)|[a-z][a-z0-9+.-]*://")
_PATH_PATTERN = re.compile(r"(?i)(?:\.\.[\\/]|/etc/|/proc/|/root/|file://|%2e%2e|[a-z]:\\\\?)")


def strip_identity_arguments(args: Mapping[str, object]) -> dict[str, object]:
    """Remove qualquer chave de identidade vinda do modelo (servidor injeta)."""
    return {key: value for key, value in args.items() if key.lower() not in IDENTITY_KEYS}


def scan_tool_arguments(args: Mapping[str, object]) -> InjectionVerdict:
    """Veredito sobre os argumentos: SQL/URL/caminho/instrucao = BLOCK."""
    for _key, value in args.items():
        if not isinstance(value, str) or not value:
            continue
        if _SQL_PATTERN.search(value):
            return InjectionVerdict(level=VerdictLevel.BLOCK, reason_code="tool_arg_sql")
        if _URL_PATTERN.search(value):
            return InjectionVerdict(level=VerdictLevel.BLOCK, reason_code="tool_arg_url")
        if _PATH_PATTERN.search(value):
            return InjectionVerdict(level=VerdictLevel.BLOCK, reason_code="tool_arg_path")
        verdict = scan_injection(value)
        if verdict.level == VerdictLevel.BLOCK:
            return InjectionVerdict(
                level=VerdictLevel.BLOCK,
                reason_code=verdict.reason_code or "tool_arg_instruction",
                matched_pattern_id=verdict.matched_pattern_id,
            )
    return InjectionVerdict(level=VerdictLevel.ALLOW)
