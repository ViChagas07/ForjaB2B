"use client";

import { useQuery } from "@tanstack/react-query";
import type { UseQueryOptions, UseQueryResult } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import type { components } from "@/core/domain/api-schema";
import type { ApiError } from "@/infrastructure/http";
import { searchApi } from "@/infrastructure/http";

import { searchKeys } from "./query-keys";
import { useDebouncedValue } from "./use-debounced-value";

type SuggestResponse = components["schemas"]["SuggestResponse"];

/** Mínimo de caracteres para consultar o suggest (igual ao backend). */
export const SUGGEST_MIN_QUERY_LENGTH = 2;
/** Debounce da digitação (ms). */
export const SUGGEST_DEBOUNCE_MS = 200;
/** Tempo de frescor do cache por (locale, termo). */
export const SUGGEST_STALE_TIME_MS = 30_000;

type SuggestQueryKey = ReturnType<typeof searchKeys.suggestions>;

export type SuggestQueryOptions = UseQueryOptions<
  SuggestResponse,
  ApiError,
  SuggestResponse,
  SuggestQueryKey
>;

/**
 * Opções da query de sugestões, extraídas do hook para serem testáveis sem
 * renderer (o projeto não tem testing-library). O `debouncedQuery` já deve
 * vir com debounce do hook.
 */
export function suggestQueryOptions(locale: string, debouncedQuery: string): SuggestQueryOptions {
  const normalized = debouncedQuery.trim();
  return {
    queryKey: searchKeys.suggestions(locale, debouncedQuery),
    queryFn: ({ signal }) => searchApi.fetchSuggestions(normalized, locale, signal),
    enabled: normalized.length >= SUGGEST_MIN_QUERY_LENGTH,
    staleTime: SUGGEST_STALE_TIME_MS,
    placeholderData: (previous) => previous,
    retry: false,
  };
}

/**
 * Sugestões do dropdown (estilo BestBuy) para a barra do header.
 *
 * Debounce de 200 ms; consulta só a partir de 2 caracteres (trim); mantém o
 * resultado anterior na tela enquanto digita (`placeholderData`) e cancela
 * requisições antigas via signal do React Query.
 */
export function useSearchSuggestions(query: string): UseQueryResult<SuggestResponse, ApiError> {
  const locale = useLocale();
  const debouncedQuery = useDebouncedValue(query, SUGGEST_DEBOUNCE_MS);
  return useQuery(suggestQueryOptions(locale, debouncedQuery));
}
