/**
 * Contratos do contexto de catálogo (neutros, sem frameworks).
 *
 * Campos em snake_case espelhando o JSON do backend. O catálogo é GLOBAL e
 * público para leitura (não requer autenticação).
 */

export const PRODUCT_STATUSES = ["ACTIVE", "INACTIVE"] as const;
export type ProductStatus = (typeof PRODUCT_STATUSES)[number];

export const CA_STATUSES = ["NOT_APPLICABLE", "VALID", "EXPIRED", "MISSING"] as const;
export type CaStatus = (typeof CA_STATUSES)[number];

export const SORT_FIELDS = ["name", "sku", "base_unit_price", "created_at"] as const;
export type SortField = (typeof SORT_FIELDS)[number];

export const SORT_ORDERS = ["asc", "desc"] as const;
export type SortOrder = (typeof SORT_ORDERS)[number];

export interface CategoryRef {
  id: string;
  name: string;
  slug: string;
}

export interface Category extends CategoryRef {
  is_active: boolean;
}

export interface BrandRef {
  id: string;
  name: string;
  slug: string;
}

export interface ProductSummary {
  id: string;
  sku: string;
  name: string;
  slug: string;
  status: ProductStatus;
  is_epi: boolean;
  ca_status: CaStatus;
  category: CategoryRef;
  brand: BrandRef | null;
  base_unit_price: string;
  currency: string;
  min_order_qty: number;
}

export interface ProductDetail extends ProductSummary {
  description: string | null;
  ca_number: string | null;
  ca_valid_until: string | null;
  ncm: string | null;
  unit_of_measure: string | null;
  weight_kg: string | null;
  attributes: Record<string, unknown> | null;
}

export interface ProductListResponse {
  items: ProductSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ProductListQuery {
  category_id?: string;
  brand_id?: string;
  status?: ProductStatus;
  is_epi?: boolean;
  q?: string;
  sort?: SortField;
  order?: SortOrder;
  page?: number;
  page_size?: number;
}
