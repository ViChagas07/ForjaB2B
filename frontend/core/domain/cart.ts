/**
 * Contratos do contexto de carrinho (neutros, sem frameworks).
 *
 * O carrinho é tenant-scoped e exige autenticação. O backend é a fonte de
 * verdade: preços/quantidades nunca são aceitos do cliente.
 */

export interface CartItem {
  product_id: string;
  sku: string;
  name: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  list_line_total?: string;
  discount_amount?: string;
  list_unit_price?: string;
  discount_percent?: string;
  discount_band?: number | null;
  units_to_volume_discount?: number | null;
  tier_min_quantity: number | null;
  image_url: string;
  image_alt: string;
  content_locale: string;
  fallback: boolean;
}

export interface Cart {
  cart_id: string;
  company_id: string;
  user_id: string;
  items: CartItem[];
  /** Subtotal final (com CNPJ). */
  subtotal: string;
  list_subtotal?: string;
  cnpj_discount_total?: string;
}

export interface AddCartItemInput {
  product_id: string;
  quantity: number;
}

export interface UpdateCartItemInput {
  quantity: number;
}
