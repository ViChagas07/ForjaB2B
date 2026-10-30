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


class EmailAlreadyExistsError(AppError):
    """Email ja cadastrado (unicidade global de login)."""

    status_code = 409
    title = "Conflict"
    code = "email_already_exists"


class ConsentRequiredError(AppError):
    """Cadastro recusado sem o aceite dos termos e da politica de privacidade."""

    status_code = 400
    title = "Bad Request"
    code = "consent_required"


class InvalidBirthDateError(AppError):
    """Data de nascimento invalida para abertura de conta de consumidor."""

    status_code = 400
    title = "Bad Request"
    code = "invalid_birth_date"


class InvalidPostalCodeError(AppError):
    """CEP ausente ou fora do formato de 8 digitos."""

    status_code = 400
    title = "Bad Request"
    code = "invalid_postal_code"


class ConsumerRegistrationUnavailableError(AppError):
    """Schema do cadastro CPF ausente (migration pendente no deploy).

    A resposta e 503 explicita para o frontend diferenciar de um bug interno e
    orientar a tentativa novamente apos a migration ser aplicada.
    """

    status_code = 503
    title = "Service Unavailable"
    code = "consumer_registration_unavailable"
