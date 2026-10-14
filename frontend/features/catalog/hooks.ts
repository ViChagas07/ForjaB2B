"use client";

import { useQuery } from "@tanstack/react-query";

import type { ProductListQuery } from "@/core/domain/catalog";
import { catalogApi, useCatalogApi } from "@/infrastructure/http";

/**
 * Hooks TanStack Query para o catálogo (somente leitura, público).
 */

export function useCategories() {
  const { listCategories } = useCatalogApi();
  return useQuery({
    queryKey: ["catalog", "categories"],
    queryFn: listCategories,
    staleTime: 5 * 60_000,
  });
}

export function useBrands() {
  const { listBrands } = useCatalogApi();
  return useQuery({
    queryKey: ["catalog", "brands"],
    queryFn: listBrands,
    staleTime: 5 * 60_000,
  });
}

export function useProducts(query: ProductListQuery) {
  const { listProducts } = useCatalogApi();
  return useQuery({
    queryKey: ["catalog", "products", query],
    queryFn: () => listProducts(query),
    placeholderData: (previous) => previous,
  });
}

export function useProduct(productId: string | undefined) {
  const { getProduct } = useCatalogApi();
  return useQuery({
    queryKey: ["catalog", "product", productId],
    queryFn: () => getProduct(productId as string),
    enabled: Boolean(productId),
  });
}
