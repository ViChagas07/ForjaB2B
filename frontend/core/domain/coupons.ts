/**
 * Contratos administrativos de cupons (snake_case espelhando a API).
 *
 * Dinheiro/percentual chegam como string (Decimal serializado no backend);
 * nunca convertemos para float para decidir regras.
 */

export const COUPON_TYPES = ["PRODUCT_TOTAL", "SHIPPING"] as const;
export type CouponType = (typeof COUPON_TYPES)[number];

export const COUPON_FILTER_STATUSES = ["ACTIVE", "EXPIRED", "EXHAUSTED"] as const;
export type CouponFilterStatus = (typeof COUPON_FILTER_STATUSES)[number];

export const COUPON_STATUSES = ["ACTIVE", "EXPIRED", "EXHAUSTED", "INACTIVE"] as const;
export type CouponStatus = (typeof COUPON_STATUSES)[number];

export const COUPON_REDEMPTION_STATUSES = ["APPLIED", "RELEASED"] as const;
export type CouponRedemptionStatus = (typeof COUPON_REDEMPTION_STATUSES)[number];

export interface CouponRedemption {
  id: string;
  order_id: string;
  company_id: string;
  amount_discounted: string;
  status: CouponRedemptionStatus;
  created_at: string;
  released_at: string | null;
}

export interface AdminCoupon {
  id: string;
  code: string;
  type: CouponType;
  percent: string;
  max_discount_amount: string | null;
  min_order_amount: string | null;
  valid_from: string | null;
  valid_until: string | null;
  usage_limit_total: number | null;
  usage_limit_per_company: number | null;
  restricted_company_id: string | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  total_uses: number;
  total_discounted: string;
}

export interface AdminCouponDetail extends AdminCoupon {
  last_redemptions: CouponRedemption[];
}

export interface AdminCouponListResponse {
  items: AdminCoupon[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AdminCouponListQuery {
  q?: string;
  status?: CouponFilterStatus;
  page?: number;
  page_size?: number;
}

export interface AdminCouponCreate {
  code?: string | null;
  type: CouponType;
  percent: string;
  max_discount_amount?: string | null;
  min_order_amount?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  usage_limit_total?: number | null;
  usage_limit_per_company?: number | null;
  restricted_company_id?: string | null;
  is_active?: boolean;
}

export interface AdminCouponUpdate {
  code?: string;
  type?: CouponType;
  percent?: string;
  max_discount_amount?: string | null;
  min_order_amount?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  usage_limit_total?: number | null;
  usage_limit_per_company?: number | null;
  restricted_company_id?: string | null;
  is_active?: boolean;
}

export interface CouponCodeResponse {
  code: string;
}
