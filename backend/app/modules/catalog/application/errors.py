"""Erros de aplicacao do contexto de catalogo (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class ProductNotFoundError(AppError):
    """Produto nao encontrado no catalogo global."""

    status_code = 404
    title = "Not Found"
    code = "product_not_found"


class CategoryNotFoundError(AppError):
    """Categoria nao encontrada no catalogo global."""

    status_code = 404
    title = "Not Found"
    code = "category_not_found"


class BrandNotFoundError(AppError):
    """Marca nao encontrada no catalogo global."""

    status_code = 404
    title = "Not Found"
    code = "brand_not_found"
