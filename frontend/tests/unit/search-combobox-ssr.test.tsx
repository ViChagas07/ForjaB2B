import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { buildCurrencyBootstrap } from "@/core/domain/currency";
import { CurrencyProvider } from "@/shared/components/currency-provider";
import { SearchCombobox } from "@/shared/components/search-combobox/search-combobox";
import { ProductPreviewList } from "@/shared/components/search-combobox/product-preview-list";
import { SuggestionList } from "@/shared/components/search-combobox/suggestion-list";

/** Traducao de teste: chave + valores serializados (suficiente p/ asserts). */
vi.mock("next-intl", () => ({
  useTranslations:
    () =>
    (key: string, values?: Record<string, unknown>): string =>
      values ? `${key} ${JSON.stringify(values)}` : key,
  useLocale: () => "pt-BR",
}));

const TERMS = [
  { text: "Capacete de Segurança Classe A Aba Frontal", kind: "product" as const },
  { text: "CAP-002", kind: "sku" as const },
  { text: "PROTEC", kind: "brand" as const },
];
const CATEGORIES = [{ name: "Proteção da Cabeça", slug: "protecao-cabeca", count: 3 }];
const PRODUCTS = [
  {
    id: "e138db51-39d4-5656-9290-63b985e0fe34",
    sku: "CAP-002",
    name: "Capacete de Segurança Classe A Aba Frontal",
    slug: "capacete-de-seguranca-classe-a-aba-frontal",
    status: "ACTIVE",
    is_epi: true,
    ca_status: "VALID",
    category: {
      id: "2bcfb27c-60e9-5043-91a5-446fbf7ef815",
      name: "Proteção da Cabeça",
      slug: "protecao-cabeca",
    },
    brand: { id: "b1", name: "PROTEC", slug: "protec" },
    base_unit_price: "29.90",
    currency: "BRL",
    min_order_qty: 1,
    price_on_request: false,
    image_url: "/catalog/photos/cap-002.webp",
    image_alt: "Capacete de Segurança Classe A Aba Frontal",
    content_locale: "pt-BR",
  },
  {
    id: "00000000-0000-0000-0000-000000000301",
    sku: "EPI-CAP-001",
    name: "Capacete de Seguranca Pro",
    slug: "capacete-de-seguranca-pro",
    status: "ACTIVE",
    is_epi: true,
    ca_status: "VALID",
    category: { id: "c2", name: "EPIs", slug: "epis" },
    brand: { id: "b1", name: "PROTEC", slug: "protec" },
    base_unit_price: null,
    currency: "BRL",
    min_order_qty: 6,
    price_on_request: true,
    image_url: "",
    image_alt: "",
    content_locale: "pt-BR",
  },
];

const noop = (): void => undefined;

describe("SuggestionList (renderização estática)", () => {
  it("renderiza termos com o trecho digitado em <strong> e categorias 'em X'", () => {
    const html = renderToStaticMarkup(
      <SuggestionList
        terms={TERMS}
        categories={CATEGORIES}
        query="cap"
        listboxId="lb"
        baseIndex={0}
        activeIndex={0}
        onActiveIndexChange={noop}
        onTermSelect={noop}
        onCategorySelect={noop}
      />,
    );
    expect(html).toContain("<strong");
    expect(html).toContain("Cap");
    // SKU com prefixo destacado: texto é dividido em partes (sem HTML injetado).
    expect(html).toContain('<strong class="font-semibold">CAP</strong>-002');
    expect(html).toContain("PROTEC");
    expect(html).toContain("Proteção da Cabeça");
    expect(html).toContain("search.inCategory");
    // Nenhuma injeção de HTML: sem script e sem atributos perigosos.
    expect(html).not.toContain("<script");
    expect(html).not.toContain("dangerouslySetInnerHTML");
  });

  it("marca aria-selected apenas no item ativo", () => {
    const html = renderToStaticMarkup(
      <SuggestionList
        terms={TERMS}
        categories={[]}
        query="cap"
        listboxId="lb"
        baseIndex={0}
        activeIndex={1}
        onActiveIndexChange={noop}
        onTermSelect={noop}
        onCategorySelect={noop}
      />,
    );
    expect(html).toContain('id="lb-opt-1"');
    expect(html).toContain('aria-selected="true"');
    const selectedCount = html.split('aria-selected="true"').length - 1;
    expect(selectedCount).toBe(1);
  });
});

describe("ProductPreviewList (renderização estática)", () => {
  it("renderiza título, nome, SKU, preço em BRL, selo de CA e pedido mínimo", () => {
    const html = renderToStaticMarkup(
      <CurrencyProvider initial={buildCurrencyBootstrap("BRL", null)}>
        <ProductPreviewList
          products={PRODUCTS}
          query="cap"
          listboxId="lb"
          baseIndex={3}
          activeIndex={null}
          onActiveIndexChange={noop}
          onProductSelect={noop}
        />
      </CurrencyProvider>,
    );
    expect(html).toContain("search.popularResultsFor");
    expect(html).toContain("Capacete de Segurança Classe A Aba Frontal");
    expect(html).toContain("CAP-002");
    expect(html).toContain("R$\u00A029,90"); // formatMoney(pt-BR, BRL) — NBSP do Intl
    expect(html).toContain("catalog.caValid");
    expect(html).toContain("catalog.priceOnRequest");
    expect(html).toContain("&quot;qty&quot;:6");
    expect(html).toContain('width="64"');
    expect(html).not.toContain("<script");
  });

  it("não renderiza nada quando não há produtos", () => {
    const html = renderToStaticMarkup(
      <CurrencyProvider initial={buildCurrencyBootstrap("BRL", null)}>
        <ProductPreviewList
          products={[]}
          query="cap"
          listboxId="lb"
          baseIndex={3}
          activeIndex={null}
          onActiveIndexChange={noop}
          onProductSelect={noop}
        />
      </CurrencyProvider>,
    );
    expect(html).toBe("");
  });
});

describe("SearchCombobox (renderização estática do form)", () => {
  it("monta o combobox ARIA fechado com sugestões disponíveis", async () => {
    vi.doMock("@/features/search/use-search-suggestions", () => ({
      useSearchSuggestions: () => ({
        data: { terms: TERMS, categories: CATEGORIES, products: PRODUCTS, query: "cap" },
        isFetching: false,
        isLoading: false,
      }),
      suggestQueryOptions: () => ({}),
      SUGGEST_MIN_QUERY_LENGTH: 2,
      SUGGEST_DEBOUNCE_MS: 200,
      SUGGEST_STALE_TIME_MS: 30_000,
    }));
    vi.doMock("@/i18n/navigation", async () => {
      const React = await import("react");
      return {
        Link: (props: { href: string; children?: React.ReactNode }) =>
          React.createElement("a", { href: props.href }, props.children),
        useRouter: () => ({ push: async () => undefined }),
      };
    });
    const { SearchCombobox: FreshCombobox } =
      await import("@/shared/components/search-combobox/search-combobox");
    const html = renderToStaticMarkup(<FreshCombobox className="w-full" inputClassName="h-10" />);
    expect(html).toContain('role="combobox"');
    expect(html).toContain('aria-autocomplete="list"');
    expect(html).toContain('aria-expanded="false"'); // painel fechado no SSR
    expect(html).toContain("nav.searchPlaceholder");
    expect(html).toContain("nav.searchSubmit");
    vi.doUnmock("@/features/search/use-search-suggestions");
    vi.doUnmock("@/i18n/navigation");
  });
});
