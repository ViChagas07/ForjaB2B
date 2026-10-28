import type { components } from "@/core/domain/api-schema";

import { apiClient } from "./client";

export type ChatRequest = components["schemas"]["ChatRequest"];
export type ChatResponse = components["schemas"]["ChatResponse"];
export type ChatProductCard = components["schemas"]["ProductCardOut"];

export interface SendChatMessageInput {
  message: string;
  conversationId: string | null;
  locale: string;
  /** Token do usuário logado; ausente = visitante (sem preço nos cartões). */
  accessToken?: string | null;
  signal?: AbortSignal;
}

/**
 * Envia uma mensagem ao assistente de IA (`POST /api/v1/ai/chat`).
 *
 * O `conversation_id` vem do estado EM MEMÓRIA do widget (nunca de
 * localStorage). Preços/cartões são montados pelo BACKEND: o cliente apenas
 * exibe. Erros chegam como `ApiError` (429/503/0/timeout) para o widget
 * traduzir em mensagem neutra.
 */
export async function sendChatMessage(input: SendChatMessageInput): Promise<ChatResponse> {
  const headers: Record<string, string> = {};
  if (input.accessToken) {
    headers.Authorization = `Bearer ${input.accessToken}`;
  }
  const response = await apiClient.request<ChatResponse>({
    method: "POST",
    path: "/api/v1/ai/chat",
    headers,
    body: {
      message: input.message,
      ...(input.conversationId ? { conversation_id: input.conversationId } : {}),
    },
    locale: input.locale,
    timeoutMs: 35_000,
    signal: input.signal,
  });
  return response.body;
}
