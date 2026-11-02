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
  // `viewerKey` separa o preco publico (prefetch do servidor) do preco
  // personalizado (empresa/CNPJ) sem misturar cache entre sessoes.
  products: (locale: string, query: ProductListQuery, viewerKey = "guest") =>
    ["catalog", "products", locale, viewerKey, query] as const,
  product: (locale: string, productId: string | undefined, viewerKey = "guest") =>
    ["catalog", "product", locale, viewerKey, productId] as const,
};
