"use client";

import { useState } from "react";

import { getApiBaseUrl } from "@/infrastructure/http";
import { cn } from "@/shared/lib/utils";

import {
  PRODUCT_IMAGE_PLACEHOLDER,
  productImageKind,
  resolveProductImageSrc,
} from "./product-image-resolve";

interface ProductImageProps {
  /** URL resolvida pelo backend (`/static/catalog/...`, `/catalog/...` ou `https://`). */
  src: string;
  alt: string;
  className?: string;
  width?: number;
  height?: number;
}

/**
 * Imagem do produto com dimensões reservadas (evita salto de layout),
 * carregamento preguiçoso e fallback para o placeholder em caso de erro.
 * Fotos preenchem o quadro (cover); ilustrações SVG aparecem inteiras
 * (contain, sobre o próprio ladrilho).
 */
export function ProductImage({
  src,
  alt,
  className,
  width = 640,
  height = 640,
}: ProductImageProps) {
  const [failed, setFailed] = useState(false);
  const resolved = failed
    ? getApiBaseUrl() + PRODUCT_IMAGE_PLACEHOLDER
    : resolveProductImageSrc(src);
  const kind = productImageKind(resolved);

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
      className={cn(
        kind === "photo" ? "object-cover" : "object-contain",
        className,
      )}
    />
  );
}
