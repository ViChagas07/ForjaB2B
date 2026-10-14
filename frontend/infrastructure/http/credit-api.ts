import type { CreditAccount, CreditEntry } from "@/core/domain/credit";
import { useLocale } from "next-intl";

import { apiClient } from "./client";

/**
 * Adapter HTTP para o contexto de crédito (`/api/v1/credit`).
 *
 * Somente leitura (conta + ledger). Reserva/liberação são internas ao backend.
 */
export const creditApi = {
  async getAccount(accessToken: string, locale: string): Promise<CreditAccount> {
    const response = await apiClient.request<CreditAccount>({
      method: "GET",
      path: "/api/v1/credit/account",
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },

  async listEntries(accessToken: string, locale: string): Promise<CreditEntry[]> {
    const response = await apiClient.request<CreditEntry[]>({
      method: "GET",
      path: "/api/v1/credit/entries",
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },
};

/** Hook para obter as funções da API com o locale atual automaticamente. */
export function useCreditApi() {
  const locale = useLocale();
  return {
    getAccount: (token: string) => creditApi.getAccount(token, locale),
    listEntries: (token: string) => creditApi.listEntries(token, locale),
  };
}
