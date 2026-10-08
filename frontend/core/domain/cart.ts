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
  tier_min_quantity: number | null;
}

export interface Cart {
  cart_id: string;
  company_id: string;
  user_id: string;
  items: CartItem[];
  subtotal: string;
}

export interface AddCartItemInput {
  product_id: string;
  quantity: number;
}

export interface UpdateCartItemInput {
  quantity: number;
}
