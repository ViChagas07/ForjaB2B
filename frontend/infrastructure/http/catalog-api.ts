import type {
  BrandRef,
  Category,
  ProductDetail,
  ProductListQuery,
  ProductListResponse,
} from "@/core/domain/catalog";

import { apiClient } from "./client";

/**
 * Adapter HTTP para os endpoints de catálogo (`/api/v1/catalog`).
 *
 * Somente leitura e global (sem autenticação). Filtros/ordenação/paginação são
 * traduzidos para query string; o backend valida por whitelist e resolve preços.
 */
export const catalogApi = {
  async listCategories(): Promise<Category[]> {
    const response = await apiClient.request<Category[]>({
      method: "GET",
      path: "/api/v1/catalog/categories",
    });
    return response.body;
  },

  async getCategory(categoryId: string): Promise<Category> {
    const response = await apiClient.request<Category>({
      method: "GET",
      path: `/api/v1/catalog/categories/${categoryId}`,
    });
    return response.body;
  },

  async listBrands(): Promise<BrandRef[]> {
    const response = await apiClient.request<BrandRef[]>({
      method: "GET",
      path: "/api/v1/catalog/brands",
    });
    return response.body;
  },

  async getBrand(brandId: string): Promise<BrandRef> {
    const response = await apiClient.request<BrandRef>({
      method: "GET",
      path: `/api/v1/catalog/brands/${brandId}`,
    });
    return response.body;
  },

  async listProducts(query: ProductListQuery = {}): Promise<ProductListResponse> {
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
    });
    return response.body;
  },

  async getProduct(productId: string): Promise<ProductDetail> {
    const response = await apiClient.request<ProductDetail>({
      method: "GET",
      path: `/api/v1/catalog/products/${productId}`,
    });
    return response.body;
  },
};
