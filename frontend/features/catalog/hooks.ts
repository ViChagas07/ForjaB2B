"use client";

import { useQuery } from "@tanstack/react-query";

import type { ProductListQuery } from "@/core/domain/catalog";
import { catalogApi } from "@/infrastructure/http";

/**
 * Hooks TanStack Query para o catálogo (somente leitura, público).
 */

export function useCategories() {
  return useQuery({
    queryKey: ["catalog", "categories"],
    queryFn: () => catalogApi.listCategories(),
    staleTime: 5 * 60_000,
  });
}

export function useBrands() {
  return useQuery({
    queryKey: ["catalog", "brands"],
    queryFn: () => catalogApi.listBrands(),
    staleTime: 5 * 60_000,
  });
}

export function useProducts(query: ProductListQuery) {
  return useQuery({
    queryKey: ["catalog", "products", query],
    queryFn: () => catalogApi.listProducts(query),
    placeholderData: (previous) => previous,
  });
}

export function useProduct(productId: string | undefined) {
  return useQuery({
    queryKey: ["catalog", "product", productId],
    queryFn: () => catalogApi.getProduct(productId as string),
    enabled: Boolean(productId),
  });
}
