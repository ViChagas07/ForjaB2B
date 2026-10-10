"""Resolucao e validacao da imagem de produto (dominio puro, sem frameworks).

Precedencia de resolucao (funcao unica e testavel):
1. ``products.image_url`` quando preenchida (foto real, Fase 9A-3);
2. imagem padrao da categoria (por slug);
3. imagem generica de placeholder.

As URLs relativas comecam por ``/`` e sao servidas pelo proprio backend
(pasta versionada ``app/static/catalog``, montada em ``/static``); URLs
absolutas exigem ``https://``. O campo e validado aqui para ser reaproveitado
pelo admin e pela importacao CSV.

As ilustracoes SVG sao originais deste projeto (sem marcas nem conteudo de
terceiros) e fazem parte do repositorio/build: nenhum arquivo e gravado em
disco em tempo de execucao. Como sao servidas pela API, o consumidor resolve o
caminho relativo contra a origem da API (o frontend usa ``NEXT_PUBLIC_API_URL``).
"""

from __future__ import annotations

from urllib.parse import urlparse

MAX_IMAGE_URL_LENGTH = 500

# Placeholder generico (quando a categoria nao tem ilustracao propria).
GENERIC_IMAGE_PATH = "/static/catalog/generic.svg"

# Imagem padrao por slug de categoria (catalogo de demonstracao).
CATEGORY_IMAGE_PATHS: dict[str, str] = {
    "epis": "/static/catalog/epis.svg",
    "protecao-cabeca": "/static/catalog/protecao-cabeca.svg",
    "protecao-visual": "/static/catalog/protecao-visual.svg",
    "protecao-maos": "/static/catalog/protecao-maos.svg",
    "protecao-respiratoria": "/static/catalog/protecao-respiratoria.svg",
    "protecao-auditiva": "/static/catalog/protecao-auditiva.svg",
    "protecao-pes": "/static/catalog/protecao-pes.svg",
    "protecao-quedas": "/static/catalog/protecao-quedas.svg",
    "maquinas-e-ferramentas": "/static/catalog/maquinas-e-ferramentas.svg",
    "ferramentas-eletricas": "/static/catalog/ferramentas-eletricas.svg",
    "maquinas-estacionarias": "/static/catalog/maquinas-estacionarias.svg",
}


def is_valid_image_url(value: str) -> bool:
    """Aceita apenas ``https://...`` ou caminho relativo iniciado por ``/``.

    Rejeita outros esquemas (``http:``, ``javascript:``, ``data:`` ...),
    caminhos protocol-relative (``//host``), vazios e acima do limite.
    """
    if not value or len(value) > MAX_IMAGE_URL_LENGTH:
        return False
    if value.startswith("/"):
        return not value.startswith("//") and len(value) > 1
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def resolve_category_image_path(category_slug: str | None) -> str:
    """Imagem padrao da categoria, ou o placeholder generico."""
    if category_slug:
        path = CATEGORY_IMAGE_PATHS.get(category_slug)
        if path is not None:
            return path
    return GENERIC_IMAGE_PATH


def resolve_product_image_path(*, product_image_url: str | None, category_slug: str | None) -> str:
    """Resolve a imagem final do produto (produto > categoria > generica)."""
    if product_image_url:
        return product_image_url
    return resolve_category_image_path(category_slug)


def resolve_image_alt(product_name: str) -> str:
    """Texto alternativo derivado do nome do produto (acessibilidade)."""
    return product_name.strip()
