"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import type { CreateOrderInput } from "@/core/domain/ordering";
import { orderingApi, useOrderingApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";

import { cartKey } from "@/features/cart";

/**
 * Chave do pedido. O locale entra na chave porque os itens do pedido trazem
 * texto traduzido pela API (snapshot do idioma da interface).
 */
export function orderKey(orderId: string, locale: string) {
  return ["orders", orderId, locale] as const;
}

/**
 * Hooks TanStack Query para pedidos (criação/consulta/cancelamento).
 */

export function useOrder(orderId: string | undefined) {
  const locale = useLocale();
  const { get } = useOrderingApi();
  return useQuery({
    queryKey: orderKey(orderId ?? "", locale),
    queryFn: () => withAuth((token) => get(token, orderId as string)),
    enabled: Boolean(orderId),
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();
  const locale = useLocale();
  const { create } = useOrderingApi();
  return useMutation({
    mutationFn: (input: CreateOrderInput) => withAuth((token) => create(token, input)),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id, locale), order);
      queryClient.invalidateQueries({ queryKey: cartKey(locale) });
      queryClient.invalidateQueries({ queryKey: ["credit"] });
    },
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();
  const locale = useLocale();
  const { cancel } = useOrderingApi();
  return useMutation({
    mutationFn: (orderId: string) => withAuth((token) => cancel(token, orderId)),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id, locale), order);
    },
  });
}
