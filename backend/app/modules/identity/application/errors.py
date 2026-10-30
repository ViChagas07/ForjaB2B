"""Erros de aplicacao do contexto de identidade (mapeados para HTTP).

Falhas de autenticacao usam AppError (status codes semanticos: 401/403) em vez
de DomainError (sempre 400), para que o contrato HTTP reflita corretamente
nao-autenticado vs. nao-autorizado. Mensagens genericas evitam enumeracao de
usuarios (nunca distinguir "email inexistente" de "senha incorreta").
"""

from __future__ import annotations

from app.core.errors import AppError


class InvalidCredentialsError(AppError):
    """Email/senha invalidos OU usuario inexistente (resposta identica)."""

    status_code = 401
    title = "Unauthorized"
    code = "invalid_credentials"


class UserInactiveError(AppError):
    """Conta ou vinculo nao esta em estado que permita autenticacao."""

    status_code = 403
    title = "Forbidden"
    code = "user_inactive"


class InvalidAccountProfileError(AppError):
    """Perfil de conta com dados invalidos (nome, data, CEP...)."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "invalid_account_profile"


class AccountNotFoundError(AppError):
    """Usuario autenticado nao encontrado no tenant."""

    status_code = 404
    title = "Not Found"
    code = "account_not_found"


class RefreshTokenRejectedError(AppError):
    """Refresh token invalido, revogado ou ja rotacionado."""

    status_code = 401
    title = "Unauthorized"
    code = "invalid_refresh_token"


class OAuthConfigurationError(AppError):
    """Configuracao OAuth obrigatoria ausente ou incompleta."""

    status_code = 503
    title = "Service Unavailable"
    code = "oauth_configuration_error"


class OAuthStateError(AppError):
    """State ausente, invalido ou ja consumido (CSRF)."""

    status_code = 400
    title = "Bad Request"
    code = "oauth_state_invalid"


class OAuthCodeError(AppError):
    """Authorization code ausente ou rejeitado pelo provedor."""

    status_code = 400
    title = "Bad Request"
    code = "oauth_code_invalid"

    def __init__(self, reason: str | None = None) -> None:
        super().__init__("Codigo OAuth invalido ou expirado.")
        # ``reason`` e o codigo publico do Google (invalid_client,
        # invalid_grant...). Nunca expor descricao/secret; o router traduz em
        # um codigo de redirect seguro para a tela de callback.
        self.reason = reason


class OAuthEmailNotVerifiedError(AppError):
    """O provedor nao confirmou a verificacao do email."""

    status_code = 403
    title = "Forbidden"
    code = "oauth_email_not_verified"


class OAuthCompanyAccountError(AppError):
    """Conta empresarial tentou entrar pelo Google (permitido apenas por senha)."""

    status_code = 403
    title = "Forbidden"
    code = "oauth_company_account"


class OAuthAccountLinkConflictError(AppError):
    """Identidade externa ja vinculada a outro usuario."""

    status_code = 409
    title = "Conflict"
    code = "oauth_account_link_conflict"


class OAuthExchangeError(AppError):
    """Exchange code ausente, expirado ou ja consumido."""

    status_code = 400
    title = "Bad Request"
    code = "oauth_exchange_invalid"
