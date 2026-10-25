import type {
  AdminProductCreate,
  AdminProductDetail,
  AdminProductListQuery,
  AdminProductListResponse,
  AdminProductSummary,
  AdminProductUpdate,
  AdminProductPublish,
  AttributeDefinitionOut,
  StaticImageOut,
  ProductTranslationAdmin,
  TranslationUpdate,
} from "@/core/domain/catalog";

import { apiClient } from "./client";
import { ApiError } from "./errors";

/**
 * Adapter HTTP para os endpoints de administração de catálogo (`/api/v1/admin/catalog`).
 *
 * Requer autenticação com papel ADMIN. Erros 409 (conflito de versão) são
 * propagados como ApiError com status 409 para tratamento específico na UI.
 */
export const adminCatalogApi = {
  async listProducts(query: AdminProductListQuery = {}): Promise<AdminProductListResponse> {
    const params = new URLSearchParams();
    if (query.q) params.set("q", query.q);
    if (query.category_id) params.set("category_id", query.category_id);
    if (query.status) params.set("status", query.status);
    if (query.page) params.set("page", String(query.page));
    if (query.page_size) params.set("page_size", String(query.page_size));

    const response = await apiClient.request<AdminProductListResponse>({
      method: "GET",
      path: `/api/v1/admin/catalog/products?${params.toString()}`,
    });
    return response.body;
  },

  async getProduct(productId: string): Promise<AdminProductDetail> {
    const response = await apiClient.request<AdminProductDetail>({
      method: "GET",
      path: `/api/v1/admin/catalog/products/${productId}`,
    });
    return response.body;
  },

  async createProduct(payload: AdminProductCreate): Promise<AdminProductDetail> {
    const response = await apiClient.request<AdminProductDetail>({
      method: "POST",
      path: "/api/v1/admin/catalog/products",
      body: payload,
    });
    return response.body;
  },

  async updateProduct(productId: string, payload: AdminProductUpdate): Promise<AdminProductDetail> {
    const response = await apiClient.request<AdminProductDetail>({
      method: "PATCH",
      path: `/api/v1/admin/catalog/products/${productId}`,
      body: payload,
    });
    return response.body;
  },

  async publishProduct(
    productId: string,
    payload: AdminProductPublish,
  ): Promise<AdminProductDetail> {
    const response = await apiClient.request<AdminProductDetail>({
      method: "POST",
      path: `/api/v1/admin/catalog/products/${productId}/publish`,
      body: payload,
    });
    return response.body;
  },

  async unpublishProduct(
    productId: string,
    payload: AdminProductPublish,
  ): Promise<AdminProductDetail> {
    const response = await apiClient.request<AdminProductDetail>({
      method: "POST",
      path: `/api/v1/admin/catalog/products/${productId}/unpublish`,
      body: payload,
    });
    return response.body;
  },

  async getAttributeDefinitions(categorySlug: string): Promise<AttributeDefinitionOut[]> {
    const response = await apiClient.request<AttributeDefinitionOut[]>({
      method: "GET",
      path: `/api/v1/admin/catalog/categories/${categorySlug}/attributes`,
    });
    return response.body;
  },

  async listStaticImages(): Promise<StaticImageOut[]> {
    const response = await apiClient.request<StaticImageOut[]>({
      method: "GET",
      path: "/api/v1/admin/catalog/static-images",
    });
    return response.body;
  },

  // Translation admin endpoints
  async listProductTranslations(productId: string): Promise<ProductTranslationAdmin[]> {
    const response = await apiClient.request<ProductTranslationAdmin[]>({
      method: "GET",
      path: `/api/v1/admin/catalog/translations/products/${productId}`,
    });
    return response.body;
  },

  async updateProductTranslation(
    productId: string,
    locale: string,
    payload: TranslationUpdate,
  ): Promise<ProductTranslationAdmin> {
    const response = await apiClient.request<ProductTranslationAdmin>({
      method: "PATCH",
      path: `/api/v1/admin/catalog/translations/products/${productId}/${locale}`,
      body: payload,
    });
    return response.body;
  },
};

/**
 * Verifica se um erro é um conflito de versão (409).
 */
export function isVersionConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

/**
 * Extrai erros de validação por campo de um ApiError (RFC 7807 com extensions).
 * Retorna mapa campo -> mensagem, ou mapa vazio se não houver detalhes por campo.
 */
export function getFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};

  const extensions = (error as any).extensions;
  if (!extensions || typeof extensions !== "object") return {};

  const fieldErrors: Record<string, string> = {};
  for (const [field, messages] of Object.entries(extensions)) {
    if (Array.isArray(messages) && messages.length > 0) {
      fieldErrors[field] = messages[0];
    } else if (typeof messages === "string") {
      fieldErrors[field] = messages;
    }
  }
  return fieldErrors;
}
