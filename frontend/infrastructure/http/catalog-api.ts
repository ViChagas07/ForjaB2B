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
  async listCategories(locale: string): Promise<Category[]> {
    const response = await apiClient.request<Category[]>({
      method: "GET",
      path: "/api/v1/catalog/categories",
      locale,
    });
    return response.body;
  },

  async getCategory(categoryId: string, locale: string): Promise<Category> {
    const response = await apiClient.request<Category>({
      method: "GET",
      path: `/api/v1/catalog/categories/${categoryId}`,
      locale,
    });
    return response.body;
  },

  async listBrands(locale: string): Promise<BrandRef[]> {
    const response = await apiClient.request<BrandRef[]>({
      method: "GET",
      path: "/api/v1/catalog/brands",
      locale,
    });
    return response.body;
  },

  async getBrand(brandId: string, locale: string): Promise<BrandRef> {
    const response = await apiClient.request<BrandRef>({
      method: "GET",
      path: `/api/v1/catalog/brands/${brandId}`,
      locale,
    });
    return response.body;
  },

  async listProducts(query: ProductListQuery = {}, locale: string): Promise<ProductListResponse> {
    const response = await apiClient.request<ProductListResponse>({
      method: "GET",
      path: "/api/v1/catalog/products",
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
    });
    return response.body;
  },

  async getProduct(productId: string, locale: string): Promise<ProductDetail> {
    const response = await apiClient.request<ProductDetail>({
      method: "GET",
      path: `/api/v1/catalog/products/${productId}`,
      locale,
    });
    return response.body;
  },
};

/** Hook para obter as funções da API com o locale atual automaticamente. */
export function useCatalogApi() {
  const locale = useLocale();
  return {
    listCategories: () => catalogApi.listCategories(locale),
    getCategory: (id: string) => catalogApi.getCategory(id, locale),
    listBrands: () => catalogApi.listBrands(locale),
    getBrand: (id: string) => catalogApi.getBrand(id, locale),
    listProducts: (query?: ProductListQuery) => catalogApi.listProducts(query, locale),
    getProduct: (id: string) => catalogApi.getProduct(id, locale),
  };
}
