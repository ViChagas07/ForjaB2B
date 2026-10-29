import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import { catalogKeys } from "@/features/catalog/query-keys";
import { parseCatalogSearchParams } from "@/features/catalog/search-params";
import {
  prefetchCatalogPage,
  prefetchHomeCatalog,
  prefetchProductDetail,
} from "@/features/catalog/server-prefetch";
import { createQueryClient } from "@/shared/lib/query-client";

type FetchInitWithNext = RequestInit & {
  next?: { revalidate?: number; tags?: string[] };
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function callFor(fetchMock: Mock, fragment: string) {
  const call = fetchMock.mock.calls.find(([input]) => String(input).includes(fragment));
  if (!call) {
    throw new Error(`fetch não chamado para ${fragment}`);
  }
  return {
    url: String(call[0]),
    init: call[1] as FetchInitWithNext,
  };
}

function happyFetch(): Mock {
  return vi.fn<typeof fetch>((input) => {
    const url = String(input);
    if (url.includes("/catalog/categories") || url.includes("/catalog/brands")) {
      return Promise.resolve(jsonResponse([]));
    }
    return Promise.resolve(jsonResponse({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }));
  });
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("prefetch do catálogo no servidor", () => {
  it("usa BACKEND_URL absoluta, lang na URL, tags e sem Authorization", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    const fetchMock = happyFetch();
    vi.stubGlobal("fetch", fetchMock);
    const client = createQueryClient();

    await prefetchHomeCatalog(client, "pt-BR", 50);

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const categories = callFor(fetchMock, "/catalog/categories");
    const brands = callFor(fetchMock, "/catalog/brands");
    const products = callFor(fetchMock, "/catalog/products");

    for (const call of [categories, brands, products]) {
      expect(call.url).toMatch(/^https:\/\/forjab2b\.onrender\.com\/api\/v1\//);
      expect(call.url).toContain("lang=pt-BR");
      expect(call.init.credentials).toBe("omit");
      expect(call.init.next?.revalidate).toBe(300);
      const headers = call.init.headers as Record<string, string> | undefined;
      expect(headers?.Authorization).toBeUndefined();
    }
    expect(categories.init.next?.tags).toContain("catalog:categories:pt-BR");
    expect(brands.init.next?.tags).toContain("catalog:brands:pt-BR");
    expect(products.init.next?.tags).toContain("catalog:products:pt-BR");

    expect(client.getQueryData(catalogKeys.categories("pt-BR"))).toEqual([]);
    expect(client.getQueryData(catalogKeys.brands("pt-BR"))).toEqual([]);
    expect(client.getQueryData(catalogKeys.products("pt-BR", { page_size: 50 }))).toEqual({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 0,
    });
  });

  it("prefetche a página do catálogo com a mesma query key do cliente", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    const fetchMock = happyFetch();
    vi.stubGlobal("fetch", fetchMock);
    const client = createQueryClient();
    const state = parseCatalogSearchParams({
      q: "capacete",
      sort: "created_at",
      order: "desc",
      page: "2",
    });

    await prefetchCatalogPage(client, "en", state);

    const products = callFor(fetchMock, "/catalog/products");
    expect(products.url).toContain("lang=en");
    expect(products.url).toContain("q=capacete");
    expect(products.url).toContain("sort=created_at");
    expect(products.url).toContain("order=desc");
    expect(products.url).toContain("page=2");
    expect(products.url).toContain("page_size=20");
    expect(client.getQueryData(catalogKeys.products("en", state.query))).toBeDefined();
  });

  it("prefetche o detalhe do produto sem quebrar a página se o backend falhar", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");
    const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new Error("cold start"));
    vi.stubGlobal("fetch", fetchMock);
    const client = createQueryClient();

    await expect(prefetchProductDetail(client, "pt-BR", "p 1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/catalog/products/p%201");
    expect(client.getQueryData(catalogKeys.product("pt-BR", "p 1"))).toBeUndefined();
  });
});
