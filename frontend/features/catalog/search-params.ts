import {
  SORT_FIELDS,
  SORT_ORDERS,
  type ProductListQuery,
  type SortField,
  type SortOrder,
} from "@/core/domain/catalog";

export const CATALOG_PAGE_SIZE = 20;

export type CatalogSearchParamsInput = Record<string, string | string[] | undefined>;

export interface CatalogSearchState {
  search: string;
  categoryId: string;
  brandId: string;
  sort: SortField;
  order: SortOrder;
  page: number;
  query: ProductListQuery;
}

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseEnum<T extends string>(
  value: string | undefined,
  allowed: readonly T[],
): T | undefined {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : undefined;
}

/**
 * Fonte única dos filtros do catálogo. O Server Component usa este parser
 * para prefetch e o CatalogBrowser usa o mesmo resultado para montar a query
 * key; assim a hidratação encontra exatamente a entrada do cache.
 */
export function parseCatalogSearchParams(params: CatalogSearchParamsInput): CatalogSearchState {
  const search = firstValue(params.q) ?? "";
  const categoryId = firstValue(params.category_id) ?? "";
  const brandId = firstValue(params.brand_id) ?? "";
  const sort = parseEnum(firstValue(params.sort), SORT_FIELDS) ?? "name";
  const order = parseEnum(firstValue(params.order), SORT_ORDERS) ?? "asc";
  const rawPage = Number(firstValue(params.page));
  const page = Number.isFinite(rawPage) && rawPage >= 1 ? Math.floor(rawPage) : 1;

  return {
    search,
    categoryId,
    brandId,
    sort,
    order,
    page,
    query: {
      q: search || undefined,
      category_id: categoryId || undefined,
      brand_id: brandId || undefined,
      sort,
      order,
      page,
      page_size: CATALOG_PAGE_SIZE,
    },
  };
}
