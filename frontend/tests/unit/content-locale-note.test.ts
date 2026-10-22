import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { showContentLocaleNote } from "@/features/catalog/content-locale";

const ROOT = process.cwd();

function source(path: string): string {
  return readFileSync(join(ROOT, path), "utf-8");
}

describe("nota de idioma do conteúdo", () => {
  it("aparece só quando o content_locale difere da interface", () => {
    expect(showContentLocaleNote("pt-BR", "pt-BR")).toBe(false);
    expect(showContentLocaleNote("en", "en")).toBe(false);
    expect(showContentLocaleNote("fr", "en")).toBe(true);
    expect(showContentLocaleNote("ar", "pt-BR")).toBe(true);
    expect(showContentLocaleNote("en", null)).toBe(false);
    expect(showContentLocaleNote("en", undefined)).toBe(false);
  });

  it("existe apenas no detalhe do produto; carrinho e pedido não exibem nota", () => {
    expect(source("features/catalog/product-detail.tsx")).toContain("catalog.contentDisplayedIn");
    expect(source("features/cart/cart-view.tsx")).not.toContain("contentDisplayedIn");
    expect(source("features/ordering/order-detail.tsx")).not.toContain("contentDisplayedIn");
    expect(source("features/cart/cart-view.tsx")).not.toContain("translationFallback");
    expect(source("features/ordering/order-detail.tsx")).not.toContain("translationFallback");
  });

  it("tem a chave nos 11 dicionários e removeu os selos antigos", () => {
    const files = ["ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt-BR", "ru", "zh-CN"];
    for (const locale of files) {
      const messages = JSON.parse(source(`messages/${locale}.json`)) as {
        catalog: Record<string, string>;
      };
      expect(messages.catalog.contentDisplayedIn, locale).toBeTruthy();
      expect(messages.catalog.fallback, locale).toBeUndefined();
      expect(messages.catalog.translationFallback, locale).toBeUndefined();
      expect(messages.catalog.translationExact, locale).toBeUndefined();
    }
  });
});
