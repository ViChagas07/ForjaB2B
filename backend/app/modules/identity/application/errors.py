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


class AntiBotVerificationError(AppError):
    """Falha na verificacao anti-bot (Turnstile), sempre generica.

    Inclui token invalido, timeout, erro de rede ou resposta inesperada da
    Cloudflare. Detalhes do provedor nunca sao expostos ao cliente.
    """

    status_code = 400
    title = "Bad Request"
    code = "antibot_verification_failed"

    def __init__(self) -> None:
        super().__init__("Nao foi possivel validar a verificacao anti-bot.")


class InvalidPasswordRecoveryRequestError(AppError):
    """Payload sem exatamente um identificador (defesa alem do schema)."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "invalid_password_recovery_request"

    def __init__(self) -> None:
        super().__init__("Informe exatamente um entre e-mail e telefone.")


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


class InvalidAvatarError(AppError):
    """Upload nao e uma imagem JPG, PNG ou WebP valida."""

    status_code = 422
    title = "Unprocessable Entity"
    code = "invalid_avatar"


class AvatarTooLargeError(AppError):
    """Imagem maior que o limite de 2 MB."""

    status_code = 413
    title = "Payload Too Large"
    code = "avatar_too_large"


class AvatarNotFoundError(AppError):
    """Avatar inexistente para a chave informada."""

    status_code = 404
    title = "Not Found"
    code = "avatar_not_found"


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


class PasswordRecoveryCodeError(AppError):
    """Codigo ausente/expirado/errado/tentativas excedidas (sempre generico)."""

    status_code = 400
    title = "Bad Request"
    code = "password_recovery_code_invalid"

    def __init__(self) -> None:
        super().__init__("Codigo invalido ou expirado.")


class PasswordResetTokenError(AppError):
    """reset_token ausente/expirado/adulterado/reutilizado (sempre generico)."""

    status_code = 400
    title = "Bad Request"
    code = "password_reset_token_invalid"

    def __init__(self) -> None:
        super().__init__("Token de redefinicao invalido ou expirado.")


class PasswordReuseError(AppError):
    """A nova senha e igual a senha atual."""

    status_code = 400
    title = "Bad Request"
    code = "password_reuse"

    def __init__(self) -> None:
        super().__init__("A nova senha deve ser diferente da senha atual.")


class PasswordRecoveryStoreError(RuntimeError):
    """Redis indisponivel no fluxo de recuperacao (fail-closed)."""


class PhoneVerificationFailedError(AppError):
    """Codigo SMS invalido/expirado ou provedor recusou, sempre generico."""

    status_code = 400
    title = "Bad Request"
    code = "phone_verification_failed"

    def __init__(self) -> None:
        super().__init__("Nao foi possivel verificar o telefone.")


class PhoneVerificationConflictError(RuntimeError):
    """Corrida de unicidade global ao reivindicar o telefone (retry interno)."""
