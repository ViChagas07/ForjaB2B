import type { AccountProfile, UpdateAccountInput } from "@/core/domain/account";

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
};
