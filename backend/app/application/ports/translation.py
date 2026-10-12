"""Porta de traducao automatica (aplicacao).

Nenhum provedor externo e adotado nesta fase: o provedor padrao e o nulo
(``NullTranslationProvider``), que nao traduz. A porta existe para permitir a
decisao futura do responsavel (API de traducao, API de LLM ou modelo local),
sem acoplar o dominio a nenhum fornecedor.

Regra: a traducao armazenada e SEMPRE a fonte servida ao cliente. Um provedor,
quando configurado, apenas gera/atualiza as traducoes offline (admin), nunca no
caminho de leitura.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.i18n import DEFAULT_LOCALE


@dataclass(frozen=True, kw_only=True)
class TranslationRequest:
    """Conteudo de origem (pt-BR) a traduzir para um idioma alvo."""

    source_locale: str
    target_locale: str
    name: str | None
    description: str | None
    attributes: dict[str, object] | None


@dataclass(frozen=True, kw_only=True)
class TranslationResult:
    """Traducao proposta por um provedor."""

    target_locale: str
    name: str | None
    description: str | None
    attributes: dict[str, object] | None


class TranslationProvider(Protocol):
    """Contrato de um provedor de traducao (offline)."""

    @property
    def name(self) -> str:
        """Identificador do provedor (ex.: ``null``)."""
        ...

    @property
    def enabled(self) -> bool:
        """Indica se o provedor realmente traduz (o nulo retorna False)."""
        ...

    async def translate(self, request: TranslationRequest) -> TranslationResult | None:
        """Traduz o conteudo; devolve ``None`` se nao puder traduzir."""
        ...


class NullTranslationProvider:
    """Provedor nulo (padrao): nao traduz nada.

    Mantem o fluxo do admin funcional sem nenhuma dependencia externa: as
    traducoes ficam a cargo do humano (edicao manual + revisao).
    """

    @property
    def name(self) -> str:
        return "null"

    @property
    def enabled(self) -> bool:
        return False

    async def translate(self, request: TranslationRequest) -> TranslationResult | None:
        return None


def is_source_locale(locale: str) -> bool:
    """True quando o idioma pedido e o proprio idioma de origem."""
    return locale == DEFAULT_LOCALE
