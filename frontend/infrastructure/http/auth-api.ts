import type { AuthSession, AuthTokens, OAuthExchangeResult } from "@/core/domain/auth";

import { apiClient } from "./client";

interface OAuthExchangeResponseBody {
  status: string;
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  user?: AuthSession["user"];
  email?: string | null;
  full_name?: string | null;
}

/**
 * Adapter HTTP para os endpoints de autenticação (`/api/v1/auth`).
 *
 * Camada fina sobre `apiClient`: apenas traduz o contrato HTTP em chamadas
 * tipadas. Erros RFC 7807 (ex.: `invalid_credentials`, `invalid_refresh_token`)
 * propagam como `ApiError` e são tratados pela UI.
 */
export const authApi = {
  async login(email: string, password: string): Promise<AuthSession> {
    const response = await apiClient.request<AuthSession>({
      method: "POST",
      path: "/api/v1/auth/login",
      body: { email, password },
    });
    return response.body;
  },

  async refresh(refreshToken: string): Promise<AuthTokens> {
    const response = await apiClient.request<AuthTokens>({
      method: "POST",
      path: "/api/v1/auth/refresh",
      body: { refresh_token: refreshToken },
    });
    return response.body;
  },

  async logout(refreshToken: string): Promise<void> {
    await apiClient.request<void>({
      method: "POST",
      path: "/api/v1/auth/logout",
      body: { refresh_token: refreshToken },
    });
  },

  async exchangeOAuthCode(code: string): Promise<OAuthExchangeResult> {
    const response = await apiClient.request<OAuthExchangeResponseBody>({
      method: "POST",
      path: "/api/v1/auth/oauth/exchange",
      body: { code },
    });
    const body = response.body;

    if (
      body.status === "authenticated" &&
      body.access_token &&
      body.refresh_token &&
      body.token_type &&
      body.expires_in !== undefined &&
      body.user
    ) {
      return {
        status: "authenticated",
        session: {
          access_token: body.access_token,
          refresh_token: body.refresh_token,
          token_type: body.token_type,
          expires_in: body.expires_in,
          user: body.user,
        },
      };
    }

    return {
      status: "onboarding",
      email: body.email ?? null,
      full_name: body.full_name ?? null,
    };
  },
};
