"""Cliente HTTP do Google OAuth (Authorization Code Flow).

Troca o authorization code por um access token do Google e le o userinfo
(``sub``/``email``/``email_verified``/``name``). Nenhum token do Google e
retornado ao chamador nem logado; apenas a identidade verificada.
"""

from __future__ import annotations

import httpx

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
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = await client.get(
                _USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            data = userinfo_response.json()

        return GoogleUserInfo(
            subject=data["sub"],
            email=data["email"],
            email_verified=bool(data.get("email_verified")),
            name=data.get("name", ""),
        )
