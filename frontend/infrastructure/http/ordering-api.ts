import type { CreateOrderInput, Order } from "@/core/domain/ordering";

import { apiClient } from "./client";

/**
 * Adapter HTTP para o contexto de pedidos (`/api/v1/orders`).
 *
 * Tenant-scoped e autenticado. Nenhum preço/total enviado pelo cliente é
 * aceito: o backend recalcura o pedido como snapshot na criação.
 */
export const orderingApi = {
  async create(accessToken: string, input: CreateOrderInput): Promise<Order> {
    const response = await apiClient.request<Order>({
      method: "POST",
      path: "/api/v1/orders",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: {
        items: input.items,
        payment_method: input.payment_method,
        idempotency_key: input.idempotency_key,
        po_number: input.po_number ?? null,
        notes: input.notes ?? null,
      },
    });
    return response.body;
  },

  async get(accessToken: string, orderId: string): Promise<Order> {
    const response = await apiClient.request<Order>({
      method: "GET",
      path: `/api/v1/orders/${orderId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async cancel(accessToken: string, orderId: string): Promise<Order> {
    const response = await apiClient.request<Order>({
      method: "POST",
      path: `/api/v1/orders/${orderId}/cancel`,
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },
};
