import type { AccountPreferences, AccountProfile, UpdateAccountInput } from "@/core/domain/account";
import type { CurrencyCode } from "@/core/domain/currency";

import { apiClient } from "./client";

export const accountApi = {
  async get(accessToken: string): Promise<AccountProfile> {
    const response = await apiClient.request<AccountProfile>({
      method: "GET",
      path: "/account",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async update(accessToken: string, input: UpdateAccountInput): Promise<AccountProfile> {
    const response = await apiClient.request<AccountProfile>({
      method: "PATCH",
      path: "/account",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: input,
    });
    return response.body;
  },

  async updatePreferences(
    accessToken: string,
    displayCurrency: CurrencyCode,
  ): Promise<AccountPreferences> {
    const response = await apiClient.request<AccountPreferences>({
      method: "PATCH",
      path: "/account/preferences",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: { display_currency: displayCurrency },
    });
    return response.body;
  },
};
