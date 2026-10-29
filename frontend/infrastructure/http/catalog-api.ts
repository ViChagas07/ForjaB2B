import type {
  BrandRef,
  Category,
  ProductDetail,
  ProductListQuery,
  ProductListResponse,
} from "@/core/domain/catalog";
import { useLocale } from "next-intl";

import { apiClient } from "./client";

/**
 * Adapter HTTP para os endpoints de catálogo (`/api/v1/catalog`).
 *
 * Somente leitura e global (sem autenticação). Filtros/ordenação/paginação são
 * traduzidos para query string; o backend valida por whitelist e resolve preços.
 */
export const catalogApi = {
  async listCategories(locale: string, signal?: AbortSignal): Promise<Category[]> {
    const response = await apiClient.request<Category[]>({
      method: "GET",
      path: "/catalog/categories",
      locale,
      signal,
    });
    return response.body;
  },

  async getCategory(categoryId: string, locale: string, signal?: AbortSignal): Promise<Category> {
    const response = await apiClient.request<Category>({
      method: "GET",
      path: `/catalog/categories/${categoryId}`,
      locale,
      signal,
    });
    return response.body;
  },

  async listBrands(locale: string, signal?: AbortSignal): Promise<BrandRef[]> {
    const response = await apiClient.request<BrandRef[]>({
      method: "GET",
      path: "/catalog/brands",
      locale,
      signal,
    });
    return response.body;
  },

  async getBrand(brandId: string, locale: string, signal?: AbortSignal): Promise<BrandRef> {
    const response = await apiClient.request<BrandRef>({
      method: "GET",
      path: `/catalog/brands/${brandId}`,
      locale,
      signal,
    });
    return response.body;
  },

  async listProducts(
    query: ProductListQuery = {},
    locale: string,
    signal?: AbortSignal,
  ): Promise<ProductListResponse> {
    const response = await apiClient.request<ProductListResponse>({
      method: "GET",
      path: "/catalog/products",
      query: {
        category_id: query.category_id,
        brand_id: query.brand_id,
        status: query.status,
        is_epi: query.is_epi,
        q: query.q,
        sort: query.sort,
        order: query.order,
        page: query.page,
        page_size: query.page_size,
      },
      locale,
      signal,
    });
    return response.body;
  },

  async getProduct(
    productId: string,
    locale: string,
    signal?: AbortSignal,
  ): Promise<ProductDetail> {
    const response = await apiClient.request<ProductDetail>({
      method: "GET",
      path: `/catalog/products/${productId}`,
      locale,
      signal,
    });
    return response.body;
  },
};

/** Hook para obter as funções da API com o locale atual automaticamente. */
export function useCatalogApi() {
  const locale = useLocale();
  return {
    listCategories: (signal?: AbortSignal) => catalogApi.listCategories(locale, signal),
    getCategory: (id: string, signal?: AbortSignal) => catalogApi.getCategory(id, locale, signal),
    listBrands: (signal?: AbortSignal) => catalogApi.listBrands(locale, signal),
    getBrand: (id: string, signal?: AbortSignal) => catalogApi.getBrand(id, locale, signal),
    listProducts: (query?: ProductListQuery, signal?: AbortSignal) =>
      catalogApi.listProducts(query, locale, signal),
    getProduct: (id: string, signal?: AbortSignal) => catalogApi.getProduct(id, locale, signal),
  };
}
