"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/shared/lib/utils";

import {
  PRODUCT_IMAGE_FALLBACK,
  PRODUCT_IMAGE_LOAD_TIMEOUT_MS,
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
 * carregamento preguiçoso e fallback local em caso de erro OU de carregamento
 * que exceda o tempo máximo (API fria/lenta não deixa o tile girando para
 * sempre). Fotos preenchem o quadro (cover); ilustrações SVG aparecem
 * inteiras (contain, sobre o próprio ladrilho).
 */
export function ProductImage({
  src,
  alt,
  className,
  width = 640,
  height = 640,
}: ProductImageProps) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [inViewport, setInViewport] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const resolved = failed ? PRODUCT_IMAGE_FALLBACK : resolveProductImageSrc(src);
  const kind = productImageKind(resolved);
  const timedOut = useRef(false);

  // Componente reutilizado com outro produto: recomeça o carregamento.
  useEffect(() => {
    timedOut.current = false;
    setFailed(false);
    setLoaded(false);
    setInViewport(false);
  }, [src]);

  // O `loading="lazy"` só inicia o download quando o tile se aproxima da
  // viewport. O timer de fallback precisa seguir o MESMO gatilho: contar os
  // 10s desde o mount fazia tiles abaixo da dobra "falharem" sem sequer
  // tentar carregar — viravam ilustração genérica para sempre (bug real do
  // dono: "as imagens não estão aparecendo").
  useEffect(() => {
    const node = imgRef.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setInViewport(true); // ambiente sem IO: comportamento anterior
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setInViewport(true);
          observer.disconnect();
        }
      },
      { rootMargin: "256px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [resolved]);

  useEffect(() => {
    if (loaded || failed || !inViewport) {
      return;
    }
    const timer = setTimeout(() => {
      if (!timedOut.current) {
        timedOut.current = true;
        setFailed(true);
      }
    }, PRODUCT_IMAGE_LOAD_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [resolved, loaded, failed, inViewport]);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      ref={imgRef}
      src={resolved}
      alt={alt}
      width={width}
      height={height}
      loading="lazy"
      decoding="async"
      onLoad={() => {
        timedOut.current = true;
        setLoaded(true);
      }}
      onError={() => {
        timedOut.current = true;
        setFailed(true);
      }}
      className={cn(kind === "photo" ? "object-cover" : "object-contain", className)}
    />
  );
}
