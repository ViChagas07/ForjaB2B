"use client";

import { useState } from "react";

import { getApiBaseUrl } from "@/infrastructure/http";

/** Placeholder genérico servido pela API em /static/catalog/generic.svg. */
const PLACEHOLDER = "/static/catalog/generic.svg";

/**
 * O backend devolve a imagem resolvida como caminho relativo à origem da API
 * (`/static/catalog/...`) ou como URL absoluta `https://`. Caminhos relativos
 * são prefixados com a base da API; URLs absolutas são usadas como estão.
 */
function resolveSrc(src: string): string {
  if (!src) {
    return getApiBaseUrl() + PLACEHOLDER;
  }
  if (/^https?:\/\//i.test(src)) {
    return src;
  }
  return getApiBaseUrl() + src;
}

interface ProductImageProps {
  /** URL resolvida pelo backend (`/static/catalog/...` ou `https://`). */
  src: string;
  alt: string;
  className?: string;
  width?: number;
  height?: number;
}

/**
 * Imagem do produto com dimensões reservadas (evita salto de layout),
 * carregamento preguiçoso e fallback para o placeholder em caso de erro.
 */
export function ProductImage({
  src,
  alt,
  className,
  width = 640,
  height = 480,
}: ProductImageProps) {
  const [failed, setFailed] = useState(false);
  const resolved = failed ? getApiBaseUrl() + PLACEHOLDER : resolveSrc(src);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={resolved}
      alt={alt}
      width={width}
      height={height}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={className}
    />
  );
}
