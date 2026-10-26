import { getApiBaseUrl } from "@/infrastructure/http";

/**
 * Placeholder final de erro, servido pela PRÓPRIA origem do frontend
 * (pasta public): nunca depende da API responder, então um tile de imagem
 * nunca fica carregando para sempre quando a API está fria/lenta.
 */
export const PRODUCT_IMAGE_FALLBACK = "/catalog/illustrations/generic.svg";

export type ProductImageKind = "photo" | "illustration";

/**
 * Origem do caminho resolvida por prefixo:
 * - `/static/...` é servido pela API (pasta app/static do backend);
 * - `/catalog/...` é servido pela origem do frontend (pasta public);
 * - `https://...` é usado como está.
 */
export function resolveProductImageSrc(src: string): string {
  if (!src) {
    return PRODUCT_IMAGE_FALLBACK;
  }
  if (/^https?:\/\//i.test(src)) {
    return src;
  }
  if (src.startsWith("/catalog/")) {
    return src;
  }
  return getApiBaseUrl() + src;
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
