/**
 * Contratos do contexto de catálogo (neutros, sem frameworks).
 *
 * Campos em snake_case espelhando o JSON do backend. O catálogo é GLOBAL e
 * público para leitura (não requer autenticação).
 */

export const PRODUCT_STATUSES = ["ACTIVE", "INACTIVE"] as const;
export type ProductStatus = (typeof PRODUCT_STATUSES)[number];

export const ADMIN_PRODUCT_STATUSES = ["DRAFT", "ACTIVE", "ARCHIVED"] as const;
export type AdminProductStatus = (typeof ADMIN_PRODUCT_STATUSES)[number];

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
  base_unit_price: string | null;
  currency: string;
  min_order_qty: number;
  price_on_request: boolean;
  image_url: string;
  image_alt: string;
  content_locale: string;
  fallback: boolean;
}

export interface ProductAttributeOut {
  key: string;
  label: string;
  value: string;
  unit: string | null;
}

export interface ProductDetail extends ProductSummary {
  description: string | null;
  ca_number: string | null;
  ca_valid_until: string | null;
  ncm: string | null;
  unit_of_measure: string | null;
  weight_kg: string | null;
  attributes: ProductAttributeOut[];
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

// --- Admin-specific types ---

export interface AdminCategoryRef {
  id: string;
  name: string;
  slug: string;
}

export interface AdminBrandRef {
  id: string;
  name: string;
  slug: string;
}

export interface AdminProductSummary {
  id: string;
  sku: string;
  name: string;
  slug: string;
  status: AdminProductStatus;
  is_epi: boolean;
  category: AdminCategoryRef;
  brand: AdminBrandRef | null;
  base_unit_price: string | null;
  currency: string;
  image_url: string | null;
  version: number;
  updated_at: string;
  updated_by: string;
}

export interface AdminProductDetail extends AdminProductSummary {
  description: string | null;
  ca_number: string | null;
  ca_valid_until: string | null;
  ncm: string | null;
  unit_of_measure: string | null;
  weight_kg: string | null;
  min_order_qty: number;
  attributes: Record<string, unknown> | null;
  created_at: string;
  created_by: string;
}

export interface AdminProductListResponse {
  items: AdminProductSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AdminProductListQuery {
  q?: string;
  category_id?: string;
  status?: AdminProductStatus;
  page?: number;
  page_size?: number;
}

export interface AttributeDefinitionOut {
  key: string;
  label: string;
  type: "text" | "number" | "enum" | "boolean";
  unit: string | null;
  options: Array<{ key: string; label: string }> | null;
  scope: string[];
  section: string;
  display_order: number;
  required: boolean;
  min_value: string | null;
  max_value: string | null;
  max_length: number | null;
}

export interface StaticImageOut {
  path: string;
  label: string;
}

export interface AdminProductCreate {
  sku: string;
  name: string;
  description: string;
  category_id: string;
  brand_id: string;
  is_epi?: boolean;
  ca_number?: string | null;
  ca_valid_until?: string | null;
  ncm?: string | null;
  unit_of_measure?: string | null;
  weight_kg?: string | null;
  min_order_qty?: number;
  base_unit_price: string;
  currency?: string;
  image_url?: string | null;
  attributes?: Record<string, unknown>;
}

export interface AdminProductUpdate {
  name?: string | null;
  description?: string | null;
  category_id?: string | null;
  brand_id?: string | null;
  is_epi?: boolean | null;
  ca_number?: string | null;
  ca_valid_until?: string | null;
  ncm?: string | null;
  unit_of_measure?: string | null;
  weight_kg?: string | null;
  min_order_qty?: number | null;
  base_unit_price?: string | null;
  currency?: string | null;
  image_url?: string | null;
  attributes?: Record<string, unknown> | null;
  version: number;
}

export interface AdminProductPublish {
  version: number;
}

// --- Translation admin types ---

export type TranslationState = "ausente" | "machine" | "reviewed" | "stale";

export interface ProductTranslationAdmin {
  locale: string;
  locale_label: string;
  state: TranslationState;
  is_stale: boolean;
  name: string | null;
  description: string | null;
  attributes: Record<string, unknown> | null;
  updated_at: string | null;
  updated_by: string | null;
}

export interface TranslationUpdate {
  name?: string | null;
  description?: string | null;
  attributes?: Record<string, unknown> | null;
  mark_reviewed?: boolean;
}
