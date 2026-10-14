"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { CreateOrderInput } from "@/core/domain/ordering";
import { orderingApi, useOrderingApi } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";

/**
 * Hooks TanStack Query para pedidos (criação/consulta/cancelamento).
 */

function orderKey(orderId: string) {
  return ["orders", orderId] as const;
}

export function useOrder(orderId: string | undefined) {
  const { get } = useOrderingApi();
  return useQuery({
    queryKey: orderKey(orderId ?? ""),
    queryFn: () => withAuth((token) => get(token, orderId as string)),
    enabled: Boolean(orderId),
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();
  const { create } = useOrderingApi();
  return useMutation({
    mutationFn: (input: CreateOrderInput) => withAuth((token) => create(token, input)),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id), order);
      queryClient.invalidateQueries({ queryKey: ["cart"] });
      queryClient.invalidateQueries({ queryKey: ["credit"] });
    },
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();
  const { cancel } = useOrderingApi();
  return useMutation({
    mutationFn: (orderId: string) => withAuth((token) => cancel(token, orderId)),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id), order);
    },
  });
}
