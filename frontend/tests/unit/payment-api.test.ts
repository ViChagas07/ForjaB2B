import { afterEach, describe, expect, it, vi } from "vitest";

import { paymentApi } from "@/infrastructure/http";

const TOKEN = "access-token";

function jsonResponse(body: unknown, init?: { status?: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("paymentApi.initiate", () => {
  it("envia Idempotency-Key no header e nao no corpo", async () => {
    const payment = { id: "pay-1", status: "PENDING", checkout_url: null };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(payment, { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    await paymentApi.initiate(
      TOKEN,
      { order_id: "order-1", method: "PIX", idempotency_key: "payment-key-0001-abcdef" },
      "pt-BR",
    );

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/payments");
    const headers = init?.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("payment-key-0001-abcdef");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body.idempotency_key).toBeUndefined();
    expect(body.order_id).toBe("order-1");
    expect(body.method).toBe("PIX");
    expect(body).not.toHaveProperty("currency");
    expect(body).not.toHaveProperty("display_currency");
    expect(body).not.toHaveProperty("rates");
    expect(Object.keys(body).sort()).toEqual(["method", "order_id"]);
  });
});
