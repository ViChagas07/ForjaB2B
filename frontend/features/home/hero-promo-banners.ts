export type HeroPromoLabelKey =
  "home.promos.episLink" | "home.promos.ferramentasLink" | "home.promos.botasLink";

export type HeroPromoLocale = "pt-BR" | "en";

export interface HeroPromoCategory {
  id: string;
  slug: string;
  name: string;
}

export interface HeroPromoImage {
  src: string;
  smallSrc: string;
  srcSet: string;
  width: number;
  height: number;
}

export interface HeroPromoImageVariant {
  sourceFile: string;
  image: HeroPromoImage;
}

export interface HeroPromoBanner {
  id: string;
  title: string;
  genre: string;
  category: HeroPromoCategory;
  href: string;
  labelKey: HeroPromoLabelKey;
  images: Record<HeroPromoLocale, HeroPromoImageVariant>;
}

const IMAGE_WIDTH = 1760;
const IMAGE_HEIGHT = 638;

function promoImage(baseName: string, height = IMAGE_HEIGHT): HeroPromoImage {
  return {
    src: `/catalog/promos/${baseName}-1760.webp`,
    smallSrc: `/catalog/promos/${baseName}-840.webp`,
    srcSet: `/catalog/promos/${baseName}-840.webp 840w, /catalog/promos/${baseName}-1760.webp 1760w`,
    width: IMAGE_WIDTH,
    height,
  };
}

export function heroPromoImageForLocale(
  banner: HeroPromoBanner,
  locale: string,
): HeroPromoImageVariant {
  return locale === "pt-BR" ? banner.images["pt-BR"] : banner.images.en;
}

export const HERO_PROMO_BANNERS: readonly HeroPromoBanner[] = [
  {
    id: "epis",
    title: "EPIs de Qualidade, Proteção Garantida",
    genre: "EPIs",
    category: {
      id: "00000000-0000-0000-0000-000000000401",
      slug: "epis",
      name: "EPIs",
    },
    href: "/catalog?category_id=00000000-0000-0000-0000-000000000401",
    labelKey: "home.promos.episLink",
    images: {
      "pt-BR": {
        sourceFile: "catalog/photos/EPIs de Qualidade, Proteção Garantida (EPIs).png",
        image: promoImage("epis"),
      },
      en: {
        sourceFile: "catalog/photos/EPIs de Qualidade, Proteção Garantida (EPIs) - English.png",
        image: promoImage("epis-en", 636),
      },
    },
  },
  {
    id: "ferramentas-eletricas",
    title: "Potência e faíscas no trabalho",
    genre: "ferramentas elétricas",
    category: {
      id: "dbde55e0-48b7-54db-aa25-a4e0162912b4",
      slug: "ferramentas-eletricas",
      name: "Ferramentas Elétricas",
    },
    href: "/catalog?category_id=dbde55e0-48b7-54db-aa25-a4e0162912b4",
    labelKey: "home.promos.ferramentasLink",
    images: {
      "pt-BR": {
        sourceFile: "catalog/photos/Potência e faíscas no trabalho (ferramentas elétricas).png",
        image: promoImage("ferramentas-eletricas"),
      },
      en: {
        sourceFile:
          "catalog/photos/Potência e faíscas no trabalho (ferramentas elétricas) - english.png",
        image: promoImage("ferramentas-eletricas-en"),
      },
    },
  },
  {
    id: "botas-de-protecao",
    title: "Botas de Proteção no Trabalho",
    genre: "botas de proteção",
    category: {
      id: "209f1617-a444-583c-9eea-5cb136a25ffb",
      slug: "protecao-pes",
      name: "Proteção dos Pés",
    },
    href: "/catalog?category_id=209f1617-a444-583c-9eea-5cb136a25ffb",
    labelKey: "home.promos.botasLink",
    images: {
      "pt-BR": {
        sourceFile: "catalog/photos/Botas de Proteção no Trabalho (botas de proteção).png",
        image: promoImage("botas-de-protecao"),
      },
      en: {
        sourceFile:
          "catalog/photos/Botas de Proteção no Trabalho (botas de proteção) - English.png",
        image: promoImage("botas-de-protecao-en"),
      },
    },
  },
];
