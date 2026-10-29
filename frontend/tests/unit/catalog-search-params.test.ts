import { describe, expect, it } from "vitest";

import { CATALOG_PAGE_SIZE, parseCatalogSearchParams } from "@/features/catalog/search-params";

describe("parseCatalogSearchParams", () => {
  it("aplica defaults estáveis para a query key e o prefetch", () => {
    const state = parseCatalogSearchParams({});

    expect(state).toMatchObject({
      search: "",
      categoryId: "",
      brandId: "",
      sort: "name",
      order: "asc",
      page: 1,
    });
    expect(state.query).toEqual({
      q: undefined,
      category_id: undefined,
      brand_id: undefined,
      sort: "name",
      order: "asc",
      page: 1,
      page_size: CATALOG_PAGE_SIZE,
    });
  });

  it("normaliza página, aceita arrays e descarta enum inválido", () => {
    const state = parseCatalogSearchParams({
      q: "capacete",
      category_id: ["cat-1", "cat-2"],
      brand_id: "brand-1",
      sort: "created_at",
      order: "desc",
      page: "2.9",
    });

    expect(state.search).toBe("capacete");
    expect(state.categoryId).toBe("cat-1");
    expect(state.brandId).toBe("brand-1");
    expect(state.sort).toBe("created_at");
    expect(state.order).toBe("desc");
    expect(state.page).toBe(2);
    expect(state.query).toEqual({
      q: "capacete",
      category_id: "cat-1",
      brand_id: "brand-1",
      sort: "created_at",
      order: "desc",
      page: 2,
      page_size: CATALOG_PAGE_SIZE,
    });
  });

  it("protege contra página inválida e valores fora das opções", () => {
    const state = parseCatalogSearchParams({
      sort: "hack",
      order: "sideways",
      page: "0",
    });

    expect(state.sort).toBe("name");
    expect(state.order).toBe("asc");
    expect(state.page).toBe(1);
  });
});
