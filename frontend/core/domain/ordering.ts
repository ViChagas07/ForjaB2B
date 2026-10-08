/**
 * Contratos do contexto de pedidos (neutros, sem frameworks).
 *
 * O pedido é um snapshot: preços/totais vêm exclusivamente do backend. As
 * formas de pagamento são simuladas (sem pagamento real).
 */

export const PAYMENT_METHODS = ["PIX", "BOLETO"] as const;
export type PaymentMethod = (typeof PAYMENT_METHODS)[number];

export const ORDER_STATUSES = [
  "RECEIVED",
  "CREDIT_REVIEW",
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

export interface CreateOrderInput {
  items: OrderItemInput[];
  payment_method: PaymentMethod;
  idempotency_key: string;
  po_number?: string | null;
  notes?: string | null;
}

export interface OrderItem {
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  base_unit_price: string | null;
  tier_min_quantity: number | null;
  line_total: string;
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
}
