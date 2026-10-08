import { afterEach, describe, expect, it, vi } from "vitest";

import { cartApi } from "@/infrastructure/http";

const TOKEN = "access-token";

function jsonResponse(body: unknown, init?: { status?: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": "application/json" },
  });
}

function emptyCart() {
  return {
    cart_id: "cart-1",
    company_id: "company-1",
    user_id: "user-1",
    items: [],
    subtotal: "0.00",
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cartApi", () => {
  it("adiciona item via POST /cart/items com auth", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(emptyCart()));
    vi.stubGlobal("fetch", fetchMock);

    await cartApi.addItem(TOKEN, { product_id: "p-1", quantity: 2 });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/cart/items");
    expect((init?.method ?? "get").toUpperCase()).toBe("POST");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer access-token");
    expect(JSON.parse(String(init?.body))).toEqual({ product_id: "p-1", quantity: 2 });
  });

  it("atualiza quantidade via PUT /cart/items/{productId}", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(emptyCart()));
    vi.stubGlobal("fetch", fetchMock);

    await cartApi.updateItem(TOKEN, "p-1", { quantity: 5 });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/cart/items/p-1");
    expect((init?.method ?? "get").toUpperCase()).toBe("PUT");
    expect(JSON.parse(String(init?.body))).toEqual({ quantity: 5 });
  });

  it("remove item via DELETE /cart/items/{productId}", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(emptyCart()));
    vi.stubGlobal("fetch", fetchMock);

    await cartApi.removeItem(TOKEN, "p-1");

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/cart/items/p-1");
    expect((init?.method ?? "get").toUpperCase()).toBe("DELETE");
  });

  it("limpa o carrinho via DELETE /cart", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(emptyCart()));
    vi.stubGlobal("fetch", fetchMock);

    await cartApi.clear(TOKEN);

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/cart");
    expect((init?.method ?? "get").toUpperCase()).toBe("DELETE");
  });
});
