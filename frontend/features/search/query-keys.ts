/**
 * Chaves de cache do suggest (dropdown da busca). O locale entra na chave
 * porque a API devolve termos/categorias/preços no idioma negociado; o termo
 * é normalizado (trim + lowercase) para "CAP", "cap " e "cap" reaproveitarem
 * a mesma entrada de cache.
 */
export const searchKeys = {
  suggestions: (locale: string, q: string) =>
    ["search", "suggestions", locale, q.trim().toLowerCase()] as const,
};
