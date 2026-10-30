// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Order } from "@/core/domain/ordering";
import { OrderDetailView } from "@/features/ordering/order-detail";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

vi.mock("@/features/ordering/hooks", () => {
  const order: Order = {
    id: "order-1",
    company_id: "company-1",
    status: "RECEIVED",
    currency: "BRL",
    subtotal: "100.00",
    discount_total: "3.00",
    shipping_total: "22.50",
    tax_total: "0.00",
    total: "119.50",
    created_at: "2026-10-30T12:00:00Z",
    content_locale: "pt-BR",
    fallback: false,
    coupon_code: "CUPOM10",
    coupon_type: "PRODUCT_TOTAL",
    coupon_percent: "10.00",
    coupon_discount_amount: "10.00",
    shipping_discount_amount: "2.50",
    items: [
      {
        sku: "CAP-002",
        product_name: "Capacete",
        quantity: 1,
        unit_price: "100.00",
        base_unit_price: "100.00",
        tier_min_quantity: 1,
        line_total: "100.00",
        content_locale: "pt-BR",
        fallback: false,
      },
    ],
  };
  return {
    useOrder: () => ({
      isLoading: false,
      isError: false,
      data: order,
    }),
    useCancelOrder: () => ({
      isPending: false,
      isError: false,
      mutate: vi.fn(),
    }),
  };
});

afterEach(cleanup);

describe("detalhe do pedido", () => {
  it("mostra o cupom e o desconto de frete com snapshots do pedido", () => {
    render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <OrderDetailView orderId="order-1" />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId("order-coupon-line").textContent).toContain("Cupom (CUPOM10)");
    expect(screen.getByTestId("order-shipping-discount-line").textContent).toContain(
      "Desconto no frete (CUPOM10)",
    );
  });
});
