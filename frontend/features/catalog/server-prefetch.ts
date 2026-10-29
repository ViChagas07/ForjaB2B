import type { QueryClient } from "@tanstack/react-query";

import type {
  BrandRef,
  Category,
  ProductDetail,
  ProductListQuery,
  ProductListResponse,
} from "@/core/domain/catalog";
import { getApiBaseUrl } from "@/infrastructure/http/config";

import { catalogKeys } from "./query-keys";
import type { CatalogSearchState } from "./search-params";

/**
 * Prefetch do catálogo público no servidor.
 *
 * Este módulo NUNCA deve ser importado por um Client Component. Ele chama a
 * API com BACKEND_URL absoluta e com o cache de dados do Next explícito.
 *
 * Regras de segurança do cache:
 * - só entram aqui categorias, marcas e produtos públicos (a API pública não
 *   recebe Authorization/cookies e não resolve preço por empresa);
 * - o locale vai em `lang` na URL, portanto entra na cache key do Next;
 * - não enviamos X-Request-ID aleatório, que invalidaria a cache key a cada
 *   request.
 */

const CATALOG_REVALIDATE_SECONDS = 300;
const SERVER_FETCH_TIMEOUT_MS = 5_000;

type CatalogTags = readonly string[];

function tagsFor(resource: string, locale: string): CatalogTags {
  return ["catalog", `catalog:${resource}:${locale}`];
}

function catalogUrl(path: string, locale: string, query?: ProductListQuery): string {
  const baseUrl = getApiBaseUrl();
  if (!/^https?:\/\//i.test(baseUrl)) {
    throw new Error("server-prefetch do catálogo só pode ser importado no servidor");
  }
  const url = new URL(`${baseUrl}${path}`);
  url.searchParams.set("lang", locale);

  if (query) {
    const orderedKeys = [
      "category_id",
      "brand_id",
      "status",
      "is_epi",
      "q",
      "sort",
      "order",
      "page",
      "page_size",
    ] as const;
    for (const key of orderedKeys) {
      const value = query[key];
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function fetchCatalogJson<T>(
  path: string,
  locale: string,
  tags: CatalogTags,
  query?: ProductListQuery,
): Promise<T> {
  const response = await fetch(catalogUrl(path, locale, query), {
    method: "GET",
    headers: {
      Accept: "application/json, application/problem+json",
      "Accept-Language": locale,
    },
    credentials: "omit",
    signal: AbortSignal.timeout(SERVER_FETCH_TIMEOUT_MS),
    next: { revalidate: CATALOG_REVALIDATE_SECONDS, tags: [...tags] },
  });

  if (!response.ok) {
    throw new Error(`catalog prefetch failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function prefetchSafely(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  queryFn: () => Promise<unknown>,
): Promise<void> {
  try {
    await queryClient.prefetchQuery({ queryKey, queryFn, retry: false });
  } catch (error) {
    // O backend pode estar acordando: o Client Component assume a busca e
    // mostra loading/erro, em vez de derrubar a página inteira.
    console.warn(
      "[catalog-prefetch] falha ao prefetchar; seguindo com o cliente:",
      error instanceof Error ? error.message : error,
    );
  }
}

export async function prefetchHomeCatalog(
  queryClient: QueryClient,
  locale: string,
  featuredPoolSize: number,
): Promise<void> {
  const featuredQuery: ProductListQuery = { page_size: featuredPoolSize };

  await Promise.all([
    prefetchSafely(queryClient, catalogKeys.categories(locale), () =>
      fetchCatalogJson<Category[]>("/catalog/categories", locale, tagsFor("categories", locale)),
    ),
    prefetchSafely(queryClient, catalogKeys.brands(locale), () =>
      fetchCatalogJson<BrandRef[]>("/catalog/brands", locale, tagsFor("brands", locale)),
    ),
    prefetchSafely(queryClient, catalogKeys.products(locale, featuredQuery), () =>
      fetchCatalogJson<ProductListResponse>(
        "/catalog/products",
        locale,
        tagsFor("products", locale),
        featuredQuery,
      ),
    ),
  ]);
}

export async function prefetchCatalogPage(
  queryClient: QueryClient,
  locale: string,
  state: CatalogSearchState,
): Promise<void> {
  await Promise.all([
    prefetchSafely(queryClient, catalogKeys.categories(locale), () =>
      fetchCatalogJson<Category[]>("/catalog/categories", locale, tagsFor("categories", locale)),
    ),
    prefetchSafely(queryClient, catalogKeys.brands(locale), () =>
      fetchCatalogJson<BrandRef[]>("/catalog/brands", locale, tagsFor("brands", locale)),
    ),
    prefetchSafely(queryClient, catalogKeys.products(locale, state.query), () =>
      fetchCatalogJson<ProductListResponse>(
        "/catalog/products",
        locale,
        tagsFor("products", locale),
        state.query,
      ),
    ),
  ]);
}

export async function prefetchProductDetail(
  queryClient: QueryClient,
  locale: string,
  productId: string,
): Promise<void> {
  await prefetchSafely(queryClient, catalogKeys.product(locale, productId), () =>
    fetchCatalogJson<ProductDetail>(`/catalog/products/${encodeURIComponent(productId)}`, locale, [
      "catalog",
      `catalog:products:${locale}`,
      `catalog:product:${productId}`,
    ]),
  );
}
