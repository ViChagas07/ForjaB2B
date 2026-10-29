"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import type { ProductListQuery } from "@/core/domain/catalog";
import { useCatalogApi } from "@/infrastructure/http";

import { catalogKeys } from "./query-keys";

/**
 * Hooks TanStack Query para o catálogo (somente leitura, público).
 *
 * O locale entra na chave de cache: a resposta vem traduzida da API e trocar
 * de idioma precisa buscar novamente (ver `catalogKeys`). O `signal` do
 * React Query é repassado ao fetch para cancelar navegações/desmontagens.
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
  const { listProducts } = useCatalogApi();
  return useQuery({
    queryKey: catalogKeys.products(locale, query),
    queryFn: ({ signal }) => listProducts(query, signal),
    placeholderData: (previous) => previous,
  });
}

export function useProduct(productId: string | undefined) {
  const locale = useLocale();
  const { getProduct } = useCatalogApi();
  return useQuery({
    queryKey: catalogKeys.product(locale, productId),
    queryFn: ({ signal }) => getProduct(productId as string, signal),
    enabled: Boolean(productId),
  });
}
