import { afterEach, describe, expect, it, vi } from "vitest";

import { adminCouponsApi } from "@/infrastructure/http";

const TOKEN = "admin-token";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function problemResponse(code: string, status: number): Response {
  return new Response(
    JSON.stringify({
      type: `urn:forja:problem:${code}`,
      title: "Conflict",
      status,
      detail: "conflict",
    }),
    {
      status,
      headers: { "content-type": "application/problem+json" },
    },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("adminCouponsApi", () => {
  it("lista com token, busca, status e paginação", async () => {
    const page = {
      items: [],
      total: 0,
      page: 2,
      page_size: 10,
      pages: 0,
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal("fetch", fetchMock);

    await adminCouponsApi.list(TOKEN, {
      q: "forja",
      status: "ACTIVE",
      page: 2,
      page_size: 10,
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/admin/coupons");
    expect(String(url)).toContain("q=forja");
    expect(String(url)).toContain("status=ACTIVE");
    expect(String(url)).toContain("page=2");
    expect(String(url)).toContain("page_size=10");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer admin-token");
  });

  it("consulta o detalhe pelo id", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ id: "coupon-1", code: "FORJA-ABC123" }));
    vi.stubGlobal("fetch", fetchMock);

    const coupon = await adminCouponsApi.get(TOKEN, "coupon-1");

    expect(coupon.code).toBe("FORJA-ABC123");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/admin/coupons/coupon-1");
  });

  it("cria com POST e payload completo", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ id: "coupon-1" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await adminCouponsApi.create(TOKEN, {
      code: "FORJA-ABC123",
      type: "PRODUCT_TOTAL",
      percent: "15.00",
      max_discount_amount: "50.00",
      is_active: true,
    });

    const [, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      code: "FORJA-ABC123",
      type: "PRODUCT_TOTAL",
      percent: "15.00",
      max_discount_amount: "50.00",
    });
  });

  it("edita com PATCH", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ id: "coupon-1", is_active: false }));
    vi.stubGlobal("fetch", fetchMock);

    await adminCouponsApi.update(TOKEN, "coupon-1", { is_active: false });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/admin/coupons/coupon-1");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toEqual({ is_active: false });
  });

  it("gera código via POST", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ code: "FORJA-XYZ234" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await adminCouponsApi.generateCode(TOKEN);

    expect(result.code).toBe("FORJA-XYZ234");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/admin/coupons/generate-code");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
  });

  it("propaga 409 tipado", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(problemResponse("coupon_conflict", 409));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      adminCouponsApi.create(TOKEN, {
        type: "PRODUCT_TOTAL",
        percent: "10.00",
      }),
    ).rejects.toMatchObject({ status: 409, type: "urn:forja:problem:coupon_conflict" });
  });
});
