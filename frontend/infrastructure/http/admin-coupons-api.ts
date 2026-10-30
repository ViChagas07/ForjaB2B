import type {
  AdminCoupon,
  AdminCouponCreate,
  AdminCouponDetail,
  AdminCouponListQuery,
  AdminCouponListResponse,
  AdminCouponUpdate,
  CouponCodeResponse,
} from "@/core/domain/coupons";

import { apiClient } from "./client";

/**
 * Adapter HTTP da administracao de cupons (`/api/v1/admin/coupons`).
 *
 * Requer access token com papel ADMIN; o token e passado explicitamente para
 * manter o mesmo padrao de `withAuth` usado nas features autenticadas.
 */
export const adminCouponsApi = {
  async list(
    accessToken: string,
    query: AdminCouponListQuery = {},
  ): Promise<AdminCouponListResponse> {
    const params = new URLSearchParams();
    if (query.q) params.set("q", query.q);
    if (query.status) params.set("status", query.status);
    if (query.page) params.set("page", String(query.page));
    if (query.page_size) params.set("page_size", String(query.page_size));

    const response = await apiClient.request<AdminCouponListResponse>({
      method: "GET",
      path: `/admin/coupons?${params.toString()}`,
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async get(accessToken: string, couponId: string): Promise<AdminCouponDetail> {
    const response = await apiClient.request<AdminCouponDetail>({
      method: "GET",
      path: `/admin/coupons/${couponId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },

  async create(accessToken: string, payload: AdminCouponCreate): Promise<AdminCoupon> {
    const response = await apiClient.request<AdminCoupon>({
      method: "POST",
      path: "/admin/coupons",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: payload,
    });
    return response.body;
  },

  async update(
    accessToken: string,
    couponId: string,
    payload: AdminCouponUpdate,
  ): Promise<AdminCoupon> {
    const response = await apiClient.request<AdminCoupon>({
      method: "PATCH",
      path: `/admin/coupons/${couponId}`,
      headers: { Authorization: `Bearer ${accessToken}` },
      body: payload,
    });
    return response.body;
  },

  async generateCode(accessToken: string): Promise<CouponCodeResponse> {
    const response = await apiClient.request<CouponCodeResponse>({
      method: "POST",
      path: "/admin/coupons/generate-code",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return response.body;
  },
};
