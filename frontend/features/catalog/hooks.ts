"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import type { ProductListQuery } from "@/core/domain/catalog";
import { catalogApi, useCatalogApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

import { catalogKeys } from "./query-keys";

/** Chave do espectador: separa visitante (prefetch publico) de sessao logada. */
export function useCatalogViewerKey(): string {
  return useAuthStore((state) => state.session?.user.id ?? "guest");
}

/**
 * Hooks TanStack Query para o catalogo (somente leitura).
 *
 * O locale e o `viewerKey` entram na chave: a resposta vem traduzida e, para
 * sessao logada, personalizada por empresa/CNPJ (refetch necessario para
 * aplicar o desconto de 15% sem depender de calculo no cliente). O `signal` do
 * React Query e repassado ao fetch para cancelar navegacoes/desmontagens.
 */

export function useCategories() {
  const locale = useLocale();
  const { listCategories } = useCatalogApi();
  return useQuery({
    queryKey: catalogKeys.categories(locale),
    queryFn: ({ signal }) => listCategories(signal),
  });
}

export function useBrands() {
  const locale = useLocale();
  const { listBrands } = useCatalogApi();
  return useQuery({
    queryKey: catalogKeys.brands(locale),
    queryFn: ({ signal }) => listBrands(signal),
  });
}

export function useProducts(query: ProductListQuery) {
  const locale = useLocale();
  const viewerKey = useCatalogViewerKey();
  const hasSession = useAuthStore((state) => Boolean(state.session));
  return useQuery({
    queryKey: catalogKeys.products(locale, query, viewerKey),
    queryFn: ({ signal }) =>
      hasSession
        ? withAuth((token) => catalogApi.listProducts(query, locale, signal, token))
        : catalogApi.listProducts(query, locale, signal),
    placeholderData: (previous) => previous,
  });
}

export function useProduct(productId: string | undefined) {
  const locale = useLocale();
  const viewerKey = useCatalogViewerKey();
  const hasSession = useAuthStore((state) => Boolean(state.session));
  return useQuery({
    queryKey: catalogKeys.product(locale, productId, viewerKey),
    queryFn: ({ signal }) =>
      hasSession
        ? withAuth((token) => catalogApi.getProduct(productId as string, locale, signal, token))
        : catalogApi.getProduct(productId as string, locale, signal),
    enabled: Boolean(productId),
  });
}
