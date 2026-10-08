import type { AddCartItemInput, Cart, UpdateCartItemInput } from "@/core/domain/cart";

import { apiClient } from "./client";

/**
 * Adapter HTTP para os endpoints de carrinho (`/api/v1/cart`).
 *
 * Tenant-scoped e autenticado: o company_id vem do token (nunca do cliente).
 * Todas as rotas devolvem o carrinho completo atualizado, com preços resolvidos
 * no servidor.
 */
export const cartApi = {
  async get(accessToken: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "GET",
      path: "/api/v1/cart",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async addItem(accessToken: string, input: AddCartItemInput): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "POST",
      path: "/api/v1/cart/items",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: { product_id: input.product_id, quantity: input.quantity },
    });
    return response.body;
  },

  async updateItem(
    accessToken: string,
    productId: string,
    input: UpdateCartItemInput,
  ): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "PUT",
      path: `/api/v1/cart/items/${productId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
      body: { quantity: input.quantity },
    });
    return response.body;
  },

  async removeItem(accessToken: string, productId: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "DELETE",
      path: `/api/v1/cart/items/${productId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async clear(accessToken: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "DELETE",
      path: "/api/v1/cart",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },
};
