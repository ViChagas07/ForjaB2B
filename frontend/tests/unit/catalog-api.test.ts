import { afterEach, describe, expect, it, vi } from "vitest";

import { catalogApi } from "@/infrastructure/http";

function jsonResponse(body: unknown, init?: { status?: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("catalogApi.listProducts", () => {
  it("serializa filtros/ordenação/paginação para a query string", async () => {
    const page = {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal("fetch", fetchMock);

    await catalogApi.listProducts({
      q: "luva",
      category_id: "cat-1",
      brand_id: "brand-1",
      sort: "base_unit_price",
      order: "desc",
      page: 2,
      page_size: 10,
    });

    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/v1/catalog/products");
    expect(url).toContain("q=luva");
    expect(url).toContain("category_id=cat-1");
    expect(url).toContain("brand_id=brand-1");
    expect(url).toContain("sort=base_unit_price");
    expect(url).toContain("order=desc");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=10");
  });

  it("omite parâmetros indefinidos", async () => {
    const page = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal("fetch", fetchMock);

    await catalogApi.listProducts({});

    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).not.toContain("q=");
    expect(url).not.toContain("category_id=");
  });
});

describe("catalogApi.getProduct", () => {
  it("consulta o detalhe do produto pelo id", async () => {
    const product = { id: "p-1", sku: "SKU-1", name: "Luva", base_unit_price: "10.50" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(product));
    vi.stubGlobal("fetch", fetchMock);

    const result = await catalogApi.getProduct("p-1");

    expect(result.id).toBe("p-1");
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/v1/catalog/products/p-1");
  });
});
