import type { components } from "@/core/domain/api-schema";

import { apiClient } from "./client";

type SuggestResponse = components["schemas"]["SuggestResponse"];

/** Resposta do endpoint de sugestões (termos, categorias e produtos). */
export type SearchSuggestResponse = SuggestResponse;

/**
 * Adapter HTTP para o endpoint de sugestões (`/api/v1/search/suggest`).
 *
 * Somente leitura e público, com auth opcional: o cookie/JWT vai pelo mesmo
 * `apiClient` do catálogo (preço por empresa resolve no backend, nunca no
 * índice) e o locale vira header `Accept-Language` da mesma forma.
 */
export const searchApi = {
  async fetchSuggestions(
    q: string,
    locale: string,
    signal?: AbortSignal,
  ): Promise<SuggestResponse> {
    const response = await apiClient.request<SuggestResponse>({
      method: "GET",
      path: "/api/v1/search/suggest",
      query: { q },
      locale,
      signal,
    });
    return response.body;
  },
};
