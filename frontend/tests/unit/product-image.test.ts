import { describe, expect, it } from "vitest";

import {
  PRODUCT_IMAGE_FALLBACK,
  productImageKind,
  resolveProductImageSrc,
} from "@/shared/components/product-image-resolve";

describe("resolucao da origem da imagem do produto", () => {
  it("caminhos /static/... permanecem same-origin (rewrite do Next encaminha ao backend)", () => {
    expect(resolveProductImageSrc("/static/catalog/protecao-cabeca.svg")).toBe(
      "/static/catalog/protecao-cabeca.svg",
    );
  });

  it("caminhos /catalog/... ficam na origem do frontend (pasta public)", () => {
    expect(resolveProductImageSrc("/catalog/photos/bot-001.webp")).toBe(
      "/catalog/photos/bot-001.webp",
    );
    expect(resolveProductImageSrc("/catalog/illustrations/esmerilhadeira.svg")).toBe(
      "/catalog/illustrations/esmerilhadeira.svg",
    );
  });

  it("URLs absolutas https sao usadas como estao (e http tambem, pois a validacao do backend decide)", () => {
    expect(resolveProductImageSrc("https://cdn.example.com/foto.webp")).toBe(
      "https://cdn.example.com/foto.webp",
    );
  });

  it("src vazio cai no fallback local do frontend (sem depender da API)", () => {
    expect(resolveProductImageSrc("")).toBe(PRODUCT_IMAGE_FALLBACK);
    expect(PRODUCT_IMAGE_FALLBACK).toBe("/catalog/illustrations/generic.svg");
  });
});

describe("tipo da imagem derivado do prefixo (sem campo novo na API)", () => {
  it("/catalog/photos/ e foto (cover)", () => {
    expect(productImageKind("/catalog/photos/bot-001.webp")).toBe("photo");
  });

  it("/catalog/illustrations/ e ilustracao (contain)", () => {
    expect(productImageKind("/catalog/illustrations/botina.svg")).toBe("illustration");
  });

  it("fallbacks da API (/static/...) e URLs absolutas sao ilustracao (contain)", () => {
    expect(productImageKind("/static/catalog/generic.svg")).toBe("illustration");
    expect(productImageKind("https://cdn.example.com/foto.webp")).toBe("illustration");
  });
});
