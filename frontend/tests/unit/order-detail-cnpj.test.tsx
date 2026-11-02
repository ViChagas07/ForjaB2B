// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildCurrencyBootstrap } from "@/core/domain/currency";
import type { Order } from "@/core/domain/ordering";
import { OrderDetailView } from "@/features/ordering/order-detail";
import { CurrencyProvider } from "@/shared/components/currency-provider";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

vi.mock("@/features/ordering/hooks", () => {
  const order: Order = {
    id: "order-cnpj",
    company_id: "company-1",
    status: "RECEIVED",
    currency: "BRL",
    subtotal: "2185.00",
    list_subtotal: "3100.00",
    cnpj_discount_total: "915.00",
    discount_total: "0.00",
    shipping_total: "0.00",
    tax_total: "0.00",
    total: "2185.00",
    created_at: "2026-11-02T12:00:00Z",
    content_locale: "pt-BR",
    fallback: false,
    items: [
      {
        sku: "CNPJ-A",
        product_name: "Luva CNPJ",
        quantity: 1,
        unit_price: "85.00",
        base_unit_price: "100.00",
        list_unit_price: "100.00",
        list_line_total: "100.00",
        cnpj_discount_percent: "15.00",
        cnpj_discount_band: 15,
        cnpj_discount_amount: "15.00",
        tier_min_quantity: null,
        line_total: "85.00",
        content_locale: "pt-BR",
        fallback: false,
      },
      {
        sku: "CNPJ-B",
        product_name: "Óculos CNPJ",
        quantity: 30,
        unit_price: "70.00",
        base_unit_price: "100.00",
        list_unit_price: "100.00",
        list_line_total: "3000.00",
        cnpj_discount_percent: "30.00",
        cnpj_discount_band: 30,
        cnpj_discount_amount: "900.00",
        tier_min_quantity: null,
        line_total: "2100.00",
        content_locale: "pt-BR",
        fallback: false,
      },
    ],
  };
  return {
    useOrder: () => ({ isLoading: false, isError: false, data: order }),
    useCancelOrder: () => ({ isPending: false, isError: false, mutate: vi.fn() }),
  };
});

afterEach(cleanup);

describe("detalhe do pedido com desconto CNPJ", () => {
  it("mostra economia total, detalhamento por item e faixas aplicadas", () => {
    const { container } = render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <CurrencyProvider initial={buildCurrencyBootstrap("BRL", null)}>
          <OrderDetailView orderId="order-cnpj" />
        </CurrencyProvider>
      </NextIntlClientProvider>,
    );

    const text = container.textContent ?? "";
    expect(text).toContain("Subtotal sem desconto");
    expect(text).toContain("3.100,00");
    expect(text).toContain("Desconto CNPJ");
    expect(text).toContain("915,00");
    expect(text).toContain("Economia com desconto CNPJ");
    expect(text).toContain("CNPJ -15%");
    expect(text).toContain("CNPJ -30%");
    expect(text).toContain("30% de desconto aplicado neste produto");
  });

  it("expõe a linha de desconto CNPJ no resumo", () => {
    render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <CurrencyProvider initial={buildCurrencyBootstrap("BRL", null)}>
          <OrderDetailView orderId="order-cnpj" />
        </CurrencyProvider>
      </NextIntlClientProvider>,
    );

    const line = screen.getByTestId("order-cnpj-discount-line").textContent ?? "";
    expect(line).toContain("Desconto CNPJ");
    expect(line).toContain("915,00");
  });
});
