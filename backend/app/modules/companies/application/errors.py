"""Erros de aplicacao do contexto de empresas (mapeados para HTTP)."""

from __future__ import annotations

from app.core.errors import AppError


class CompanyAlreadyExistsError(AppError):
    """CNPJ ja cadastrado (unicidade global garantida pela constraint)."""

    status_code = 409
    title = "Conflict"
    code = "company_already_exists"


class CompanyNotFoundError(AppError):
    """Empresa do tenant autenticado nao encontrada."""

    status_code = 404
    title = "Not Found"
    code = "company_not_found"


class CpfAlreadyExistsError(AppError):
    """CPF ja cadastrado (um CPF, uma conta)."""

    status_code = 409
    title = "Conflict"
    code = "cpf_already_exists"
