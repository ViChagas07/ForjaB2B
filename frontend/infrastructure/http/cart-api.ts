import type { AddCartItemInput, Cart, UpdateCartItemInput } from "@/core/domain/cart";
import { useLocale } from "next-intl";

import { apiClient } from "./client";

/**
 * Adapter HTTP para os endpoints de carrinho (`/api/v1/cart`).
 *
 * Tenant-scoped e autenticado: o company_id vem do token (nunca do cliente).
 * Todas as rotas devolvem o carrinho completo atualizado, com preços resolvidos
 * no servidor.
 */
export const cartApi = {
  async get(accessToken: string, locale: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "GET",
      path: "/api/v1/cart",
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },

  async addItem(accessToken: string, input: AddCartItemInput, locale: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "POST",
      path: "/api/v1/cart/items",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: { product_id: input.product_id, quantity: input.quantity },
      locale,
    });
    return response.body;
  },

  async updateItem(
    accessToken: string,
    productId: string,
    input: UpdateCartItemInput,
    locale: string,
  ): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "PUT",
      path: `/api/v1/cart/items/${productId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
      body: { quantity: input.quantity },
      locale,
    });
    return response.body;
  },

  async removeItem(accessToken: string, productId: string, locale: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "DELETE",
      path: `/api/v1/cart/items/${productId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },

  async clear(accessToken: string, locale: string): Promise<Cart> {
    const response = await apiClient.request<Cart>({
      method: "DELETE",
      path: "/api/v1/cart",
      headers: { Authorization: `Bearer ${accessToken}` },
      locale,
    });
    return response.body;
  },
};

/** Hook para obter as funções da API com o locale atual automaticamente. */
export function useCartApi() {
  const locale = useLocale();
  return {
    get: (token: string) => cartApi.get(token, locale),
    addItem: (token: string, input: AddCartItemInput) => cartApi.addItem(token, input, locale),
    updateItem: (token: string, productId: string, input: UpdateCartItemInput) =>
      cartApi.updateItem(token, productId, input, locale),
    removeItem: (token: string, productId: string) => cartApi.removeItem(token, productId, locale),
    clear: (token: string) => cartApi.clear(token, locale),
  };
}
