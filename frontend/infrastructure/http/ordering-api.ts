import type { CreateOrderInput, Order } from "@/core/domain/ordering";
import { useLocale } from "next-intl";

import { apiClient } from "./client";

/**
 * Adapter HTTP para o contexto de pedidos (`/api/v1/orders`).
 *
 * Tenant-scoped e autenticado. Nenhum preço/total enviado pelo cliente é
 * aceito: o backend recalcura o pedido como snapshot na criação.
 */
export const orderingApi = {
  async create(accessToken: string, input: CreateOrderInput, locale: string): Promise<Order> {
    const response = await apiClient.request<Order>({
      method: "POST",
      path: "/api/v1/orders",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Idempotency-Key": input.idempotency_key,
      },
      body: {
        items: input.items,
        payment_method: input.payment_method,
        po_number: input.po_number ?? null,
        notes: input.notes ?? null,
      },
      locale,
    });
    return response.body;
  },

  async get(accessToken: string, orderId: string, locale: string): Promise<Order> {
    const response = await apiClient.request<Order>({
      method: "GET",
      path: `/api/v1/orders/${orderId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },

  async cancel(accessToken: string, orderId: string, locale: string): Promise<Order> {
    const response = await apiClient.request<Order>({
      method: "POST",
      path: `/api/v1/orders/${orderId}/cancel`,
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },
};

/** Hook para obter as funções da API com o locale atual automaticamente. */
export function useOrderingApi() {
  const locale = useLocale();
  return {
    create: (token: string, input: CreateOrderInput) => orderingApi.create(token, input, locale),
    get: (token: string, orderId: string) => orderingApi.get(token, orderId, locale),
    cancel: (token: string, orderId: string) => orderingApi.cancel(token, orderId, locale),
  };
}
