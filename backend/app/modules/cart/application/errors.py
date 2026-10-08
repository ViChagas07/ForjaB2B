"""Erros de aplicacao do contexto de carrinho (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class ProductNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "product_not_found"


class ProductNotSellableError(AppError):
    """Produto inativo ou EPI com CA expirado/ausente."""

    status_code = 409
    title = "Conflict"
    code = "product_not_sellable"


class QuantityBelowMinimumError(AppError):
    """Quantidade abaixo do lote minimo do produto."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "quantity_below_minimum"


class CartNotFoundError(AppError):
    status_code = 404
    title = "Not Found"
    code = "cart_not_found"
