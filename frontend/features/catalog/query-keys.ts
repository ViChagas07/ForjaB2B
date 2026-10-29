import type { ProductListQuery } from "@/core/domain/catalog";

/**
 * Chaves de cache do catálogo. O locale faz parte da chave porque a API
 * devolve nome/descrição/atributos traduzidos conforme `Accept-Language`;
 * sem ele, trocar de idioma reaproveitaria o conteúdo do idioma anterior.
 * Em produtos, todos os filtros/paginação/ordenação entram na chave.
 */
export const catalogKeys = {
  categories: (locale: string) => ["catalog", "categories", locale] as const,
  brands: (locale: string) => ["catalog", "brands", locale] as const,
  products: (locale: string, query: ProductListQuery) =>
    ["catalog", "products", locale, query] as const,
  product: (locale: string, productId: string | undefined) =>
    ["catalog", "product", locale, productId] as const,
};
