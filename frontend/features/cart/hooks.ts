"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AddCartItemInput, UpdateCartItemInput } from "@/core/domain/cart";
import { cartApi, useCartApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

const CART_QUERY_KEY = ["cart"] as const;

/**
 * Hooks TanStack Query para o carrinho (tenant-scoped, autenticado).
 *
 * O backend é a fonte de verdade: toda mutação devolve o carrinho atualizado e
 * invalida/atualiza o cache em memória. Nenhum estado de carrinho vive no
 * Zustand/localStorage.
 */

export function useCart() {
  const status = useAuthStore((s) => s.status);
  const { get } = useCartApi();
  return useQuery({
    queryKey: CART_QUERY_KEY,
    queryFn: () => withAuth((token) => get(token)),
    enabled: status === "authenticated",
  });
}

export function useAddCartItem() {
  const queryClient = useQueryClient();
  const { addItem } = useCartApi();
  return useMutation({
    mutationFn: (input: AddCartItemInput) => withAuth((token) => addItem(token, input)),
    onSuccess: (cart) => {
      queryClient.setQueryData(CART_QUERY_KEY, cart);
    },
  });
}

export function useUpdateCartItem() {
  const queryClient = useQueryClient();
  const { updateItem } = useCartApi();
  return useMutation({
    mutationFn: ({ productId, input }: { productId: string; input: UpdateCartItemInput }) =>
      withAuth((token) => updateItem(token, productId, input)),
    onSuccess: (cart) => {
      queryClient.setQueryData(CART_QUERY_KEY, cart);
    },
  });
}

export function useRemoveCartItem() {
  const queryClient = useQueryClient();
  const { removeItem } = useCartApi();
  return useMutation({
    mutationFn: (productId: string) => withAuth((token) => removeItem(token, productId)),
    onSuccess: (cart) => {
      queryClient.setQueryData(CART_QUERY_KEY, cart);
    },
  });
}

export function useClearCart() {
  const queryClient = useQueryClient();
  const { clear } = useCartApi();
  return useMutation({
    mutationFn: () => withAuth((token) => clear(token)),
    onSuccess: (cart) => {
      queryClient.setQueryData(CART_QUERY_KEY, cart);
    },
  });
}
