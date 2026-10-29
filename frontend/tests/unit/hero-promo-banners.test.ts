import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { HERO_PROMO_BANNERS, heroPromoImageForLocale } from "@/features/home/hero-promo-banners";

const PUBLIC_DIR = join(process.cwd(), "public");

function baselineFile(path: string): string {
  return join(PUBLIC_DIR, path.replace(/^\//, ""));
}

describe("banners promocionais do hero", () => {
  it("extrai o gênero do nome de cada arquivo e o mantém associado à imagem", () => {
    for (const banner of HERO_PROMO_BANNERS) {
      for (const variant of Object.values(banner.images)) {
        const match = variant.sourceFile.match(/\(([^)]+)\)(?: - [Ee]nglish)?\.png$/);
        expect(match?.[1], variant.sourceFile).toBe(banner.genre);
        expect(existsSync(baselineFile(variant.sourceFile))).toBe(true);
      }
    }
  });

  it("usa a arte em português apenas no pt-BR e a arte em inglês nos demais idiomas", () => {
    for (const banner of HERO_PROMO_BANNERS) {
      expect(heroPromoImageForLocale(banner, "pt-BR")).toBe(banner.images["pt-BR"]);
      expect(heroPromoImageForLocale(banner, "en")).toBe(banner.images.en);
      expect(heroPromoImageForLocale(banner, "ar")).toBe(banner.images.en);
      expect(heroPromoImageForLocale(banner, "es")).toBe(banner.images.en);
      expect(heroPromoImageForLocale(banner, "ja")).toBe(banner.images.en);
    }
  });

  it("aponta para categorias reais do catálogo", () => {
    expect(
      HERO_PROMO_BANNERS.map((banner) => ({
        genre: banner.genre,
        slug: banner.category.slug,
        href: banner.href,
      })),
    ).toEqual([
      {
        genre: "EPIs",
        slug: "epis",
        href: "/catalog?category_id=00000000-0000-0000-0000-000000000401",
      },
      {
        genre: "ferramentas elétricas",
        slug: "ferramentas-eletricas",
        href: "/catalog?category_id=dbde55e0-48b7-54db-aa25-a4e0162912b4",
      },
      {
        genre: "botas de proteção",
        slug: "protecao-pes",
        href: "/catalog?category_id=209f1617-a444-583c-9eea-5cb136a25ffb",
      },
    ]);

    for (const banner of HERO_PROMO_BANNERS) {
      expect(banner.href).toBe(`/catalog?category_id=${banner.category.id}`);
    }
  });

  it("usa imagens otimizadas locais com dimensões definidas", () => {
    for (const banner of HERO_PROMO_BANNERS) {
      for (const variant of Object.values(banner.images)) {
        const { image } = variant;
        expect(existsSync(baselineFile(image.src))).toBe(true);
        expect(existsSync(baselineFile(image.smallSrc))).toBe(true);
        expect(image.srcSet).toContain(`${image.smallSrc} 840w`);
        expect(image.srcSet).toContain(`${image.src} 1760w`);
        expect(image.width / image.height).toBeGreaterThan(2.75);
        expect(image.width / image.height).toBeLessThan(2.78);
      }
    }
  });

  it("não repete identificadores nem destinos", () => {
    expect(new Set(HERO_PROMO_BANNERS.map((banner) => banner.id)).size).toBe(
      HERO_PROMO_BANNERS.length,
    );
    expect(new Set(HERO_PROMO_BANNERS.map((banner) => banner.href)).size).toBe(
      HERO_PROMO_BANNERS.length,
    );
  });
});
