/**
 * Placeholder final de erro, servido pela PRÓPRIA origem do frontend
 * (pasta public): nunca depende da API responder, então um tile de imagem
 * nunca fica carregando para sempre quando a API está fria/lenta.
 */
export const PRODUCT_IMAGE_FALLBACK = "/catalog/illustrations/generic.svg";

export type ProductImageKind = "photo" | "illustration";

/**
 * Caminhos relativos do backend (`/static/...`) e do frontend (`/catalog/...`)
 * são servidos na MESMA origem: `/static` é encaminhado pelo rewrite do Next
 * para o backend, então nenhuma URL absoluta de API entra no bundle.
 */
export function resolveProductImageSrc(src: string): string {
  return src || PRODUCT_IMAGE_FALLBACK;
}

/**
 * Tipo da imagem derivado do prefixo do caminho (sem campo novo na API):
 * fotos preenchem o quadro (cover); ilustrações aparecem inteiras (contain).
 */
export function productImageKind(src: string): ProductImageKind {
  return src.startsWith("/catalog/photos/") ? "photo" : "illustration";
}

/** Tempo máximo (ms) esperando o carregamento de uma imagem antes do fallback. */
export const PRODUCT_IMAGE_LOAD_TIMEOUT_MS = 10_000;
