import { QueryClient } from "@tanstack/react-query";

/**
 * Defaults do TanStack Query (server state).
 *
 * - staleTime de 5 min: navegar entre páginas reutiliza o cache das mesmas
 *   query keys (locale + parâmetros) em vez de refazer as 3 chamadas;
 * - gcTime de 30 min mantém entradas inativas no cache durante a sessão;
 * - retry 1 cobre uma falha transitória sem multiplicar a espera do cold start;
 * - refetchOnWindowFocus desligado evita requisições redundantes ao voltar
 *   para a aba.
 */

export const DEFAULT_QUERY_DEFAULTS = {
  staleTime: 5 * 60_000,
  gcTime: 30 * 60_000,
  refetchOnWindowFocus: false,
  retry: 1,
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

let browserQueryClient: QueryClient | undefined;

/**
 * Padrão oficial do App Router: no servidor cada requisição recebe um
 * QueryClient novo; no navegador ele é um singleton durante a sessão.
 */
export function getQueryClient(): QueryClient {
  if (typeof window === "undefined") {
    return createQueryClient();
  }
  if (!browserQueryClient) {
    browserQueryClient = createQueryClient();
  }
  return browserQueryClient;
}
