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
  coupon_code: "FORJA-ABC123",
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

    const result = await orderingApi.create(TOKEN, CREATE_INPUT, "pt-BR");

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/orders");
    expect((init?.method ?? "get").toUpperCase()).toBe("POST");
    const headers = init?.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("idem-1");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body.idempotency_key).toBeUndefined();
    expect(body.payment_method).toBe("BOLETO");
    expect(body.coupon_code).toBe("FORJA-ABC123");
    expect(body).not.toHaveProperty("currency");
    expect(body).not.toHaveProperty("display_currency");
    expect(body).not.toHaveProperty("rates");
    expect(Object.keys(body).sort()).toEqual([
      "coupon_code",
      "items",
      "notes",
      "payment_method",
      "po_number",
    ]);
    expect(result.id).toBe("o-1");
  });
});

describe("orderingApi.previewCoupon", () => {
  it("envia código/pagamento e devolve a simulação", async () => {
    const preview = {
      valid: true,
      reason: null,
      missing_amount: null,
      subtotal: "100.00",
      recovery_discount: "0.00",
      coupon_discount: "10.00",
      shipping_discount: "0.00",
      shipping_total: "25.00",
      pix_discount: "5.75",
      total: "109.25",
      applied_discounts: ["COUPON_PRODUCT", "PIX"],
      currency: "BRL",
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(preview));
    vi.stubGlobal("fetch", fetchMock);

    const result = await orderingApi.previewCoupon(
      TOKEN,
      { code: "CUPOM10", payment_method: "PIX" },
      "pt-BR",
    );

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/orders/coupon-preview");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      code: "CUPOM10",
      payment_method: "PIX",
    });
    expect(result.total).toBe("109.25");
  });
});

describe("orderingApi.cancel", () => {
  it("cancela pedido via POST /orders/{id}/cancel", async () => {
    const order = { id: "o-1", status: "CANCELLED", currency: "BRL", total: "20.00" };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(order));
    vi.stubGlobal("fetch", fetchMock);

    await orderingApi.cancel(TOKEN, "o-1", "pt-BR");

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

    await orderingApi.get(TOKEN, "o-1", "pt-BR");

    const [url] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/orders/o-1");
  });
});
