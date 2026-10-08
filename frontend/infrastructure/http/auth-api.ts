import type { AuthSession, AuthTokens } from "@/core/domain/auth";

import { apiClient } from "./client";

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
};
