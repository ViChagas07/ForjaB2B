/**
 * Contratos do contexto de pedidos (neutros, sem frameworks).
 *
 * O pedido é um snapshot: preços/totais vêm exclusivamente do backend. PIX e
 * Boleto são simulados; CARD usa o Stripe Checkout quando habilitado no
 * backend (redirect para página hospedada do Stripe).
 */

export const PAYMENT_METHODS = ["PIX", "CARD", "BOLETO"] as const;
export type PaymentMethod = (typeof PAYMENT_METHODS)[number];

export const ORDER_STATUSES = [
  "RECEIVED",
  "CREDIT_REVIEW",
  "PAID",
  "INVOICED",
  "IN_TRANSIT",
  "DELIVERED",
  "CANCELLED",
  "CREDIT_REJECTED",
] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

export interface OrderItemInput {
  product_id: string;
  quantity: number;
}

export const COUPON_REJECTION_REASONS = [
  "NOT_FOUND",
  "INACTIVE",
  "NOT_STARTED",
  "EXPIRED",
  "EXHAUSTED",
  "COMPANY_LIMIT_REACHED",
  "MIN_ORDER_NOT_MET",
  "NOT_ALLOWED_FOR_COMPANY",
] as const;
export type CouponRejectionReason = (typeof COUPON_REJECTION_REASONS)[number];

export const COUPON_DISCOUNT_KINDS = [
  "RECOVERY",
  "COUPON_PRODUCT",
  "COUPON_SHIPPING",
  "PIX",
] as const;
export type CouponDiscountKind = (typeof COUPON_DISCOUNT_KINDS)[number];

export interface CouponPreviewInput {
  code?: string | null;
  payment_method: PaymentMethod;
}

export interface CouponPreview {
  valid: boolean;
  reason: CouponRejectionReason | null;
  missing_amount: string | null;
  subtotal: string | null;
  recovery_discount: string | null;
  coupon_discount: string | null;
  shipping_discount: string | null;
  shipping_total: string | null;
  pix_discount: string | null;
  total: string | null;
  applied_discounts: CouponDiscountKind[];
  currency: string;
}

export interface CreateOrderInput {
  items: OrderItemInput[];
  payment_method: PaymentMethod;
  idempotency_key: string;
  po_number?: string | null;
  notes?: string | null;
  coupon_code?: string | null;
}

export interface OrderItem {
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  base_unit_price: string | null;
  tier_min_quantity: number | null;
  line_total: string;
  content_locale: string;
  fallback: boolean;
}

export interface Order {
  id: string;
  company_id: string;
  status: OrderStatus;
  currency: string;
  subtotal: string;
  discount_total: string;
  shipping_total: string;
  tax_total: string;
  total: string;
  items: OrderItem[];
  created_at: string;
  content_locale: string;
  fallback: boolean;
  coupon_code?: string | null;
  coupon_type?: "PRODUCT_TOTAL" | "SHIPPING" | null;
  coupon_percent?: string | null;
  coupon_discount_amount?: string;
  shipping_discount_amount?: string;
}
