import { afterEach, describe, expect, it, vi } from "vitest";

import { creditApi } from "@/infrastructure/http";

const TOKEN = "access-token";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("creditApi", () => {
  it("consulta a conta via GET /credit/account", async () => {
    const account = {
      company_id: "c-1",
      credit_limit: "1000.00",
      used: "200.00",
      available: "800.00",
      currency: "BRL",
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(account));
    vi.stubGlobal("fetch", fetchMock);

    const result = await creditApi.getAccount(TOKEN);

    expect(result.available).toBe("800.00");
    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/credit/account");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer access-token");
  });

  it("lista o ledger via GET /credit/entries", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await creditApi.listEntries(TOKEN);

    const [url] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/credit/entries");
  });
});
