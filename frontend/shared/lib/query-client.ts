import { QueryClient } from "@tanstack/react-query";

/**
 * Defaults sensatos para o TanStack Query (server state).
 *
 * - staleTime curto o bastante para não servir dados velhos;
 * - gcTime de 5 min libera o cache de queries inativas;
 * - retry baixo para falhas transitórias, sem mascarar erros reais;
 * - refetchOnWindowFocus desligado (evita requisições redundantes).
 */

export const DEFAULT_QUERY_DEFAULTS = {
  staleTime: 30_000,
  gcTime: 5 * 60_000,
  retry: 1,
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
