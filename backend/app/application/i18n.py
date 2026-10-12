"""Resolucao de conteudo traduzido (camada de aplicacao, compartilhada).

Une a traducao armazenada (tabela ``product_translations``) com a origem
(pt-BR) aplicando a regra de fallback campo a campo do dominio. Usada pelo
catalogo, pela busca e pelo carrinho para nao duplicar a regra.

Nenhuma traducao e gerada aqui: apenas se escolhe o texto a servir.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.i18n import DEFAULT_LOCALE, ResolvedText, resolve_attributes, resolve_text


@dataclass(frozen=True, kw_only=True)
class ProductTextTranslation:
    """Traducao armazenada relevante para a resposta (DTO neutro)."""

    name: str | None = None
    description: str | None = None
    attributes: dict[str, object] | None = None


@dataclass(frozen=True, kw_only=True)
class ResolvedProductText:
    """Texto final de um produto no idioma resolvido."""

    name: ResolvedText
    description: ResolvedText
    attributes: dict[str, object] | None
    content_locale: str
    fallback: bool


def resolve_product_text(
    *,
    source_name: str,
    source_description: str | None,
    source_attributes: dict[str, object] | None,
    locale: str,
    translation: ProductTextTranslation | None,
) -> ResolvedProductText:
    """Resolve nome, descricao e atributos com fallback campo a campo.

    ``content_locale`` e o idioma efetivamente entregue; ``fallback`` indica que
    ao menos um campo veio do pt-BR (ou que nao havia traducao).
    """
    name = resolve_text(
        source=source_name,
        translated=translation.name if translation else None,
        locale=locale,
    )
    description = resolve_text(
        source=source_description,
        translated=translation.description if translation else None,
        locale=locale,
    )
    attributes, attributes_fallback = resolve_attributes(
        source=source_attributes,
        translated=translation.attributes if translation else None,
        locale=locale,
    )
    if locale == DEFAULT_LOCALE:
        content_locale = DEFAULT_LOCALE
        fallback = False
    elif translation is None:
        content_locale = DEFAULT_LOCALE
        fallback = True
    else:
        content_locale = locale
        fallback = name.fallback or description.fallback or attributes_fallback
    return ResolvedProductText(
        name=name,
        description=description,
        attributes=attributes,
        content_locale=content_locale,
        fallback=fallback,
    )
