import { QueryClient } from "@tanstack/react-query";

/**
 * Defaults sensatos para o TanStack Query (server state).
 *
 * - staleTime curto o bastante para não servir dados velhos;
 * - gcTime de 5 min libera o cache de queries inativas;
 * - retry com backoff exponencial cobre a janela de cold start/redeploy do
 *   backend hospedado (plano gratuito dorme após ociosidade): 5 tentativas
 *   com timeout de 15 s cada + 1-8 s de espera ≈ até ~90 s de tolerância,
 *   em vez de falhar com "Falha de conexão" nos primeiros 30 s;
 * - refetchOnWindowFocus desligado (evita requisições redundantes).
 */

export const DEFAULT_QUERY_DEFAULTS = {
  staleTime: 30_000,
  gcTime: 5 * 60_000,
  retry: 4,
  retryDelay: (attempt: number) => Math.min(1000 * 2 ** attempt, 8000),
  refetchOnWindowFocus: false,
  refetchOnReconnect: true,
} as const;

export const DEFAULT_MUTATION_DEFAULTS = {
  retry: 0,
} as const;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { ...DEFAULT_QUERY_DEFAULTS },
      mutations: { ...DEFAULT_MUTATION_DEFAULTS },
    },
  });
}
