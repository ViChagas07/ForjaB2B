import { afterEach, describe, expect, it, vi } from "vitest";

import { adminCatalogApi, isVersionConflict, getFieldErrors } from "@/infrastructure/http";
import { ApiError } from "@/infrastructure/http/errors";

function jsonResponse(body: unknown, init?: { status?: number; contentType?: string }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": init?.contentType ?? "application/json" },
  });
}

function problemResponse(body: unknown, init?: { status?: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 400,
    headers: { "content-type": "application/problem+json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("adminCatalogApi.listProducts", () => {
  it("serializa filtros e paginação para a query string", async () => {
    const page = {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal("fetch", fetchMock);

    await adminCatalogApi.listProducts({
      q: "luva",
      category_id: "cat-1",
      status: "ACTIVE",
      page: 2,
      page_size: 10,
    });

    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/v1/admin/catalog/products");
    expect(url).toContain("q=luva");
    expect(url).toContain("category_id=cat-1");
    expect(url).toContain("status=ACTIVE");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=10");
  });

  it("omite parâmetros indefinidos", async () => {
    const page = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal("fetch", fetchMock);

    await adminCatalogApi.listProducts({});

    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).not.toContain("q=");
    expect(url).not.toContain("category_id=");
    expect(url).not.toContain("status=");
  });
});

describe("adminCatalogApi.getProduct", () => {
  it("consulta o detalhe do produto pelo id", async () => {
    const product = { id: "p-1", sku: "SKU-1", name: "Luva", status: "DRAFT" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(product));
    vi.stubGlobal("fetch", fetchMock);

    const result = await adminCatalogApi.getProduct("p-1");

    expect(result.id).toBe("p-1");
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/v1/admin/catalog/products/p-1");
  });
});

describe("adminCatalogApi.createProduct", () => {
  it("envia payload completo para criar produto", async () => {
    const created = { id: "p-new", sku: "NEW-1", name: "Novo", status: "DRAFT" };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(created, { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const payload = {
      sku: "NEW-1",
      name: "Novo",
      description: "Descrição",
      category_id: "cat-1",
      brand_id: "brand-1",
      base_unit_price: "10.00",
    };

    const result = await adminCatalogApi.createProduct(payload);

    expect(result.sku).toBe("NEW-1");
    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const init = call?.[1];
    expect(init?.method).toBe("POST");
    const body = JSON.parse(init?.body as string);
    expect(body.sku).toBe("NEW-1");
    expect(body.name).toBe("Novo");
  });
});

describe("adminCatalogApi.updateProduct", () => {
  it("envia payload parcial com version para atualizar", async () => {
    const updated = { id: "p-1", sku: "SKU-1", name: "Atualizado", version: 1234567890 };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(updated));
    vi.stubGlobal("fetch", fetchMock);

    const payload = { name: "Atualizado", version: 1234567890 };

    const result = await adminCatalogApi.updateProduct("p-1", payload);

    expect(result.name).toBe("Atualizado");
    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const init = call?.[1];
    expect(init?.method).toBe("PATCH");
    const body = JSON.parse(init?.body as string);
    expect(body.name).toBe("Atualizado");
    expect(body.version).toBe(1234567890);
  });
});

describe("adminCatalogApi.publishProduct / unpublishProduct", () => {
  it("publica produto enviando version", async () => {
    const published = { id: "p-1", sku: "SKU-1", name: "Produto", status: "ACTIVE" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(published));
    vi.stubGlobal("fetch", fetchMock);

    const result = await adminCatalogApi.publishProduct("p-1", { version: 1234567890 });

    expect(result.status).toBe("ACTIVE");
    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const url = call?.[0];
    const init = call?.[1];
    expect(String(url)).toContain("/publish");
    expect(init?.method).toBe("POST");
  });

  it("despublica produto enviando version", async () => {
    const unpublished = { id: "p-1", sku: "SKU-1", name: "Produto", status: "DRAFT" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(unpublished));
    vi.stubGlobal("fetch", fetchMock);

    const result = await adminCatalogApi.unpublishProduct("p-1", { version: 1234567890 });

    expect(result.status).toBe("DRAFT");
    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const url = call?.[0];
    expect(String(url)).toContain("/unpublish");
  });
});

describe("adminCatalogApi.getAttributeDefinitions", () => {
  it("busca definições de atributo por slug de categoria", async () => {
    const defs = [
      {
        key: "modelo",
        label: "Modelo",
        type: "text" as const,
        unit: null,
        options: null,
        scope: ["protecao-maos"],
        section: "Detalhes",
        display_order: 1,
        required: false,
        min_value: null,
        max_value: null,
        max_length: 100,
      },
    ];
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(defs));
    vi.stubGlobal("fetch", fetchMock);

    const result = await adminCatalogApi.getAttributeDefinitions("protecao-maos");

    expect(result).toHaveLength(1);
    expect(result[0]!.key).toBe("modelo");
    const calls = fetchMock.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    const url = calls[0]?.[0];
    expect(url).toBeDefined();
    expect(String(url)).toContain("/api/v1/admin/catalog/categories/protecao-maos/attributes");
  });
});

describe("adminCatalogApi.listStaticImages", () => {
  it("lista imagens estáticas disponíveis", async () => {
    const images = [{ path: "/static/catalog/luva.jpg", label: "Luva" }];
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(images));
    vi.stubGlobal("fetch", fetchMock);

    const result = await adminCatalogApi.listStaticImages();

    expect(result).toHaveLength(1);
    expect(result[0]!.path).toBe("/static/catalog/luva.jpg");
    const calls = fetchMock.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    const url = calls[0]?.[0];
    expect(url).toBeDefined();
    expect(String(url)).toContain("/api/v1/admin/catalog/static-images");
  });
});

describe("isVersionConflict", () => {
  it("retorna true para ApiError com status 409", () => {
    const error = new ApiError({
      type: "urn:forja:problem:conflict",
      title: "Conflict",
      status: 409,
    });
    expect(isVersionConflict(error)).toBe(true);
  });

  it("retorna false para outros status", () => {
    const error400 = new ApiError({
      type: "urn:forja:problem:bad_request",
      title: "Bad Request",
      status: 400,
    });
    const error404 = new ApiError({
      type: "urn:forja:problem:not_found",
      title: "Not Found",
      status: 404,
    });
    expect(isVersionConflict(error400)).toBe(false);
    expect(isVersionConflict(error404)).toBe(false);
  });

  it("retorna false para erros não-ApiError", () => {
    expect(isVersionConflict(new Error("generic"))).toBe(false);
    expect(isVersionConflict(null)).toBe(false);
    expect(isVersionConflict({})).toBe(false);
  });
});

describe("getFieldErrors", () => {
  it("extrai erros por campo das extensions do Problem Details", () => {
    const error = new ApiError({
      type: "urn:forja:problem:validation_error",
      title: "Validation Error",
      status: 422,
      extensions: {
        name: ["Nome é obrigatório"],
        sku: ["SKU já existe"],
        attributes: ["Chave desconhecida: 'foo'"],
      },
    });

    const fields = getFieldErrors(error);
    expect(fields.name).toBe("Nome é obrigatório");
    expect(fields.sku).toBe("SKU já existe");
    expect(fields.attributes).toBe("Chave desconhecida: 'foo'");
  });

  it("retorna objeto vazio para ApiError sem extensions", () => {
    const error = new ApiError({
      type: "urn:forja:problem:conflict",
      title: "Conflict",
      status: 409,
    });
    expect(getFieldErrors(error)).toEqual({});
  });

  it("retorna objeto vazio para erros não-ApiError", () => {
    expect(getFieldErrors(new Error("network"))).toEqual({});
    expect(getFieldErrors(null)).toEqual({});
  });

  it("ignora valores não-string/não-array nas extensions", () => {
    const error = new ApiError({
      type: "urn:forja:problem:validation_error",
      title: "Validation Error",
      status: 422,
      extensions: {
        name: "Nome inválido",
        sku: 123,
        description: { nested: "object" },
      },
    });

    const fields = getFieldErrors(error);
    expect(fields.name).toBe("Nome inválido");
    expect(fields.sku).toBeUndefined();
    expect(fields.description).toBeUndefined();
  });
});
