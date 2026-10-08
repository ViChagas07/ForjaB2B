import type { CreditAccount, CreditEntry } from "@/core/domain/credit";

import { apiClient } from "./client";

/**
 * Adapter HTTP para o contexto de crédito (`/api/v1/credit`).
 *
 * Somente leitura (conta + ledger). Reserva/liberação são internas ao backend.
 */
export const creditApi = {
  async getAccount(accessToken: string): Promise<CreditAccount> {
    const response = await apiClient.request<CreditAccount>({
      method: "GET",
      path: "/api/v1/credit/account",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async listEntries(accessToken: string): Promise<CreditEntry[]> {
    const response = await apiClient.request<CreditEntry[]>({
      method: "GET",
      path: "/api/v1/credit/entries",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },
};
