import { afterEach, describe, expect, it, vi } from "vitest";

import { orderingApi } from "@/infrastructure/http";
import type { CreateOrderInput } from "@/core/domain/ordering";

const TOKEN = "access-token";

function jsonResponse(body: unknown, init?: { status?: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": "application/json" },
  });
}

const CREATE_INPUT: CreateOrderInput = {
  items: [{ product_id: "p-1", quantity: 2 }],
  payment_method: "BOLETO",
  idempotency_key: "idem-1",
  po_number: null,
  notes: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("orderingApi.create", () => {
  it("cria pedido via POST /orders com idempotency_key", async () => {
    const order = {
      id: "o-1",
      company_id: "c-1",
      status: "RECEIVED",
      currency: "BRL",
      subtotal: "20.00",
      discount_total: "0.00",
      shipping_total: "0.00",
      tax_total: "0.00",
      total: "20.00",
      items: [],
      created_at: "2026-01-01T00:00:00Z",
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(order, { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await orderingApi.create(TOKEN, CREATE_INPUT);

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/orders");
    expect((init?.method ?? "get").toUpperCase()).toBe("POST");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body.idempotency_key).toBe("idem-1");
    expect(body.payment_method).toBe("BOLETO");
    expect(result.id).toBe("o-1");
  });
});

describe("orderingApi.cancel", () => {
  it("cancela pedido via POST /orders/{id}/cancel", async () => {
    const order = { id: "o-1", status: "CANCELLED", currency: "BRL", total: "20.00" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(order));
    vi.stubGlobal("fetch", fetchMock);

    await orderingApi.cancel(TOKEN, "o-1");

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/orders/o-1/cancel");
    expect((init?.method ?? "get").toUpperCase()).toBe("POST");
  });
});

describe("orderingApi.get", () => {
  it("consulta pedido via GET /orders/{id}", async () => {
    const order = { id: "o-1", status: "RECEIVED", currency: "BRL", total: "20.00" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(order));
    vi.stubGlobal("fetch", fetchMock);

    await orderingApi.get(TOKEN, "o-1");

    const [url] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/orders/o-1");
  });
});
