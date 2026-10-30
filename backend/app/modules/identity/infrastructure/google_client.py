"""Cliente HTTP do Google OAuth (Authorization Code Flow).

Troca o authorization code por um access token do Google e le o userinfo
(``sub``/``email``/``email_verified``/``name``). Nenhum token do Google e
retornado ao chamador nem logado; apenas a identidade verificada.
"""

from __future__ import annotations

import httpx

from app.modules.identity.application.errors import OAuthCodeError
from app.modules.identity.application.ports import GoogleIdentityClient, GoogleUserInfo

_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105 - endpoint publico
_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleIdentityClientImpl(GoogleIdentityClient):
    """Implementacao concreta via httpx (integracoes reais ficam aqui)."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri

    async def exchange_authorization_code(self, code: str) -> GoogleUserInfo:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_response = await client.post(
                    _TOKEN_ENDPOINT,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": self._redirect_uri,
                    },
                )
                if token_response.is_error:
                    raise OAuthCodeError(reason=_google_error_reason(token_response))

                access_token = token_response.json().get("access_token")
                if not access_token:
                    raise OAuthCodeError(reason="missing_access_token")

                userinfo_response = await client.get(
                    _USERINFO_ENDPOINT,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if userinfo_response.is_error:
                    raise OAuthCodeError(reason="userinfo_error")
                data = userinfo_response.json()
        except OAuthCodeError:
            raise
        except httpx.HTTPError as exc:
            raise OAuthCodeError(reason="network_error") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise OAuthCodeError(reason="invalid_provider_response") from exc

        return GoogleUserInfo(
            subject=data["sub"],
            email=data["email"],
            email_verified=bool(data.get("email_verified")),
            name=data.get("name", ""),
        )


def _google_error_reason(response: httpx.Response) -> str | None:
    """Le apenas o codigo de erro publico do Google (nunca a descricao)."""
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    reason = body.get("error")
    return reason if isinstance(reason, str) else None
