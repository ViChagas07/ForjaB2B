import { getApiBaseUrl } from "@/infrastructure/http";

/** Placeholder genérico servido pela API em /static/catalog/generic.svg. */
export const PRODUCT_IMAGE_PLACEHOLDER = "/static/catalog/generic.svg";

export type ProductImageKind = "photo" | "illustration";

/**
 * Origem do caminho resolvida por prefixo:
 * - `/static/...` é servido pela API (pasta app/static do backend);
 * - `/catalog/...` é servido pela origem do frontend (pasta public);
 * - `https://...` é usado como está.
 */
export function resolveProductImageSrc(src: string): string {
  if (!src) {
    return getApiBaseUrl() + PRODUCT_IMAGE_PLACEHOLDER;
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
