// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { buildCurrencyBootstrap, type FxRatesSnapshot } from "@/core/domain/currency";
import { CatalogPrice } from "@/features/catalog/catalog-price";
import { CurrencyProvider } from "@/shared/components/currency-provider";
import { PriceDisplay } from "@/shared/components/price-display";
import { RateDisclosure } from "@/shared/components/rate-disclosure";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

const SNAPSHOT: FxRatesSnapshot = {
  rates: {
    BRL: "1",
    USD: "0.18408",
    EUR: "0.16477",
    GBP: "0.13738",
    CAD: "0.25713",
    AUD: "0.26204",
    JPY: "28.946",
    CNY: "1.2246",
  },
  rateDate: "2026-10-30",
  source: "Frankfurter / European Central Bank",
  stale: false,
};

function renderWithCurrency(currency: string, ui: ReactNode) {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <CurrencyProvider initial={buildCurrencyBootstrap(currency, SNAPSHOT)}>{ui}</CurrencyProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(cleanup);

describe("PriceDisplay", () => {
  it("mostra valor convertido com ≈ e a cobrança em R$ como secundária", () => {
    const { container } = renderWithCurrency(
      "USD",
      <PriceDisplay amount="100" primary="converted" showSecondary />,
    );

    const text = container.textContent ?? "";
    expect(text).toContain("US$");
    expect(text).toContain("18,41");
    expect(text).toContain("Cobrança em R$");
    expect(text).toContain("100,00");
  });

  it("com BRL não mostra ≈ nem linha secundária", () => {
    const { container } = renderWithCurrency(
      "BRL",
      <PriceDisplay amount="100" primary="converted" showSecondary />,
    );

    expect(container.textContent).toContain("R$");
    expect(container.textContent).toContain("100,00");
    expect(container.textContent).not.toContain("≈");
    expect(container.textContent).not.toContain("Cobrança em");
  });

  it("no checkout usa R$ como principal e o convertido como secundário", () => {
    const { container } = renderWithCurrency(
      "USD",
      <PriceDisplay amount="119.50" primary="brl" showSecondary />,
    );

    expect(container.textContent).toContain("R$");
    expect(container.textContent).toContain("119,50");
    expect(container.textContent).toContain("≈");
    expect(container.textContent).toContain("US$");
    expect(container.textContent).toContain("22,00");
  });

  it("valor nulo não renderiza", () => {
    const { container } = renderWithCurrency(
      "USD",
      <PriceDisplay amount={null} primary="converted" />,
    );
    expect(container.textContent).toBe("");
  });

  it("o mesmo valor tem a mesma conversão no catálogo e no carrinho", () => {
    const catalog = renderWithCurrency("USD", <CatalogPrice amount="100" priceOnRequest={false} />);
    const catalogText = catalog.container.textContent ?? "";
    catalog.unmount();

    const cart = renderWithCurrency(
      "USD",
      <PriceDisplay amount="100" primary="converted" showSecondary />,
    );
    const cartText = cart.container.textContent ?? "";

    expect(catalogText).toContain("18,41");
    expect(cartText).toContain("18,41");
  });
});

describe("RateDisclosure", () => {
  it("fica oculto quando a moeda é BRL", () => {
    renderWithCurrency("BRL", <RateDisclosure />);
    expect(screen.queryByTestId("rate-disclosure")).toBeNull();
  });

  it("mostra fonte e data de referência quando há conversão", () => {
    renderWithCurrency("USD", <RateDisclosure />);

    const text = screen.getByTestId("rate-disclosure").textContent ?? "";
    expect(text).toContain("Frankfurter / European Central Bank");
    expect(text).toContain("30 de out. de 2026");
    expect(text).toContain("Atualizadas a cada 12 horas");
  });

  it("avisa quando a taxa está desatualizada", () => {
    render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <CurrencyProvider initial={buildCurrencyBootstrap("USD", { ...SNAPSHOT, stale: true })}>
          <RateDisclosure />
        </CurrencyProvider>
      </NextIntlClientProvider>,
    );

    expect(screen.getByTestId("rate-disclosure").textContent).toContain(
      "A taxa pode estar desatualizada",
    );
  });
});

describe("CatalogPrice", () => {
  it("converte o preço do catálogo para a moeda escolhida", () => {
    const { container } = renderWithCurrency(
      "USD",
      <CatalogPrice amount="100" priceOnRequest={false} />,
    );

    expect(container.textContent).toContain("≈");
    expect(container.textContent).toContain("18,41");
    expect(container.textContent).not.toContain("Cobrança em");
  });

  it("mostra a cobrança em R$ no detalhe do produto", () => {
    const { container } = renderWithCurrency(
      "USD",
      <CatalogPrice amount="100" priceOnRequest={false} showBrl />,
    );

    expect(container.textContent).toContain("≈");
    expect(container.textContent).toContain("Cobrança em R$");
  });
});
