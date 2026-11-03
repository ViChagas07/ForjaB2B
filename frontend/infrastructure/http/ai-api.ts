import type { components } from "@/core/domain/api-schema";

import { apiClient } from "./client";

const HEALTH_TTL_MS = 30_000;
const HEALTH_TIMEOUT_MS = 4_000;

export interface LlmHealth {
  available: boolean;
  enabled: boolean;
  model: string;
}

let healthCache: { value: LlmHealth; at: number } | null = null;
let healthInFlight: Promise<LlmHealth> | null = null;

/**
 * Consulta `/health/llm` com cache de ~30 s (inclusive falhas).
 *
 * O endpoint e separado de `/health`: LM Studio fora do ar nunca derruba a
 * API. A funcao NUNCA rejeita — devolve `available=false` para o widget
 * mostrar o modo demonstracao em vez de erro.
 */
export async function getLlmHealth(force = false): Promise<LlmHealth> {
  if (!force && healthCache && Date.now() - healthCache.at < HEALTH_TTL_MS) {
    return healthCache.value;
  }
  if (healthInFlight) return healthInFlight;
  healthInFlight = fetchLlmHealth().finally(() => {
    healthInFlight = null;
  });
  return healthInFlight;
}

async function fetchLlmHealth(): Promise<LlmHealth> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  try {
    const response = await fetch("/health/llm", {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    const payload = response.ok
      ? ((await response.json()) as Partial<LlmHealth>)
      : ({} satisfies Partial<LlmHealth>);
    const value: LlmHealth = {
      available: payload.available === true,
      enabled: payload.enabled === true,
      model: typeof payload.model === "string" ? payload.model : "",
    };
    healthCache = { value, at: Date.now() };
    return value;
  } catch {
    const value: LlmHealth = { available: false, enabled: false, model: "" };
    healthCache = { value, at: Date.now() };
    return value;
  } finally {
    clearTimeout(timer);
  }
}

export type ChatRequest = components["schemas"]["ChatRequest"];
/** `degraded` sinaliza LLM local desligado/indisponivel (modo demonstracao). */
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
    path: "/ai/chat",
    headers,
    body: {
      message: input.message,
      ...(input.conversationId ? { conversation_id: input.conversationId } : {}),
    },
    locale: input.locale,
    // Cobre o timeout do LLM (60 s) + margem; o modelo local responde em
    // poucos segundos, mas o primeiro carregamento pode demorar.
    timeoutMs: 65_000,
    signal: input.signal,
  });
  return response.body;
}
