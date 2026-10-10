"""Testes unitarios da imagem de produto (dominio puro)."""

from __future__ import annotations

from app.domain.catalog_image import (
    CATEGORY_IMAGE_PATHS,
    GENERIC_IMAGE_PATH,
    MAX_IMAGE_URL_LENGTH,
    is_valid_image_url,
    resolve_category_image_path,
    resolve_image_alt,
    resolve_product_image_path,
)


def test_aceita_https_e_caminho_relativo() -> None:
    assert is_valid_image_url("https://cdn.example.com/foto.jpg")
    assert is_valid_image_url("/catalog/capacete.svg")


def test_rejeita_esquemas_e_formatos_invalidos() -> None:
    assert not is_valid_image_url("javascript:alert(1)")
    assert not is_valid_image_url("data:image/svg+xml;base64,AAAA")
    assert not is_valid_image_url("http://inseguro.example.com/x.png")
    assert not is_valid_image_url("//host-protocol-relative/x.png")
    assert not is_valid_image_url("ftp://example.com/x")
    assert not is_valid_image_url("")
    assert not is_valid_image_url("/")


def test_rejeita_url_gigante() -> None:
    assert not is_valid_image_url("https://example.com/" + "a" * MAX_IMAGE_URL_LENGTH)


def test_resolucao_precedencia_produto_categoria_generico() -> None:
    # Imagem do produto vence tudo.
    assert (
        resolve_product_image_path(
            product_image_url="https://cdn.example.com/x.jpg", category_slug="protecao-cabeca"
        )
        == "https://cdn.example.com/x.jpg"
    )
    # Sem imagem do produto: usa a imagem da categoria conhecida.
    assert (
        resolve_product_image_path(product_image_url=None, category_slug="protecao-cabeca")
        == CATEGORY_IMAGE_PATHS["protecao-cabeca"]
    )
    # Categoria desconhecida ou ausente: placeholder generico.
    assert (
        resolve_product_image_path(product_image_url=None, category_slug="inexistente")
        == GENERIC_IMAGE_PATH
    )
    assert (
        resolve_product_image_path(product_image_url=None, category_slug=None) == GENERIC_IMAGE_PATH
    )


def test_categoria_sem_mapeamento_usa_generico() -> None:
    assert resolve_category_image_path("nao-existe") == GENERIC_IMAGE_PATH


def test_alt_deriva_do_nome() -> None:
    assert resolve_image_alt("  Capacete de Segurança  ") == "Capacete de Segurança"
