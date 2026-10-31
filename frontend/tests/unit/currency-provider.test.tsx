// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { hydrateRoot } from "react-dom/client";
import { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildCurrencyBootstrap,
  type CurrencyBootstrap,
  type FxRatesSnapshot,
} from "@/core/domain/currency";
import { CurrencyProvider, useCurrency } from "@/shared/components/currency-provider";
import { formatBrl, formatMoney } from "@/shared/lib/money";

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

function bootstrap(currency: string): CurrencyBootstrap {
  return buildCurrencyBootstrap(currency, SNAPSHOT);
}

function Probe() {
  const { currency, rates, setCurrency } = useCurrency();
  const amount = `${currency}|${formatMoney("100", {
    currency,
    locale: "pt-BR",
    rates,
  })}|${formatBrl("100", "pt-BR")}`;

  return (
    <div>
      <span data-testid="probe">{amount}</span>
      <button type="button" onClick={() => setCurrency("USD")}>
        Trocar para USD
      </button>
      <button type="button" onClick={() => setCurrency("JPY")}>
        Trocar para JPY
      </button>
    </div>
  );
}

function MetaProbe() {
  const { source, rateDate, stale } = useCurrency();
  return <span data-testid="meta">{`${source}|${rateDate}|${stale}`}</span>;
}

afterEach(() => {
  cleanup();
  document.cookie = "forja_currency=; Max-Age=0; Path=/";
});

describe("CurrencyProvider", () => {
  it("renderiza no cliente exatamente o texto do primeiro paint do servidor", () => {
    const initial = bootstrap("USD");
    const serverHtml = renderToStaticMarkup(
      <CurrencyProvider initial={initial}>
        <Probe />
      </CurrencyProvider>,
    );
    const serverText = serverHtml.replace(/<[^>]*>/g, "");

    const { container } = render(
      <CurrencyProvider initial={initial}>
        <Probe />
      </CurrencyProvider>,
    );

    expect(container.textContent).toBe(serverText);
    expect(screen.getByTestId("probe").textContent).toContain("≈");
  });

  it("hidrata o mesmo markup sem erro de mismatch", async () => {
    const initial = bootstrap("USD");
    const html = renderToStaticMarkup(
      <CurrencyProvider initial={initial}>
        <Probe />
      </CurrencyProvider>,
    );
    const container = document.createElement("div");
    container.innerHTML = html;
    const errors: string[] = [];
    const errorSpy = vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
      errors.push(args.map(String).join(" "));
    });

    let root: ReturnType<typeof hydrateRoot> | undefined;
    await act(async () => {
      root = hydrateRoot(
        container,
        <CurrencyProvider initial={initial}>
          <Probe />
        </CurrencyProvider>,
      );
    });
    root?.unmount();
    errorSpy.mockRestore();

    expect(errors.filter((message) => /hydrat/i.test(message))).toEqual([]);
  });

  it("expõe fonte, data de referência e stale para a UI", () => {
    render(
      <CurrencyProvider initial={{ ...buildCurrencyBootstrap("USD", SNAPSHOT), stale: true }}>
        <MetaProbe />
      </CurrencyProvider>,
    );

    expect(screen.getByTestId("meta").textContent).toBe(
      "Frankfurter / European Central Bank|2026-10-30|true",
    );
  });

  it("troca a moeda no estado e persiste no cookie sem recarregar", () => {
    render(
      <CurrencyProvider initial={bootstrap("BRL")}>
        <Probe />
      </CurrencyProvider>,
    );

    expect(screen.getByTestId("probe").textContent).toContain("R$");

    fireEvent.click(screen.getByRole("button", { name: "Trocar para USD" }));

    expect(screen.getByTestId("probe").textContent).toContain("USD|");
    expect(screen.getByTestId("probe").textContent).toContain("18,41");
    expect(document.cookie).toContain("forja_currency=USD");
  });

  it("cookie invalido cai em BRL", () => {
    render(
      <CurrencyProvider initial={buildCurrencyBootstrap("CHF", SNAPSHOT)}>
        <Probe />
      </CurrencyProvider>,
    );

    expect(screen.getByTestId("probe").textContent).toContain("BRL|");
    expect(screen.getByTestId("probe").textContent).toContain("R$");
  });

  it("taxa ausente cai em BRL mesmo com moeda valida no cookie", () => {
    const initial = buildCurrencyBootstrap("USD", {
      ...SNAPSHOT,
      rates: { BRL: "1" },
    });
    render(
      <CurrencyProvider initial={initial}>
        <Probe />
      </CurrencyProvider>,
    );

    expect(screen.getByTestId("probe").textContent).toContain("BRL|");
    expect(screen.getByTestId("probe").textContent).not.toContain("≈");
  });

  it("setCurrency com valor fora da lista tambem cai em BRL", () => {
    render(
      <CurrencyProvider initial={bootstrap("USD")}>
        <InvalidSetterProbe />
      </CurrencyProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Valor invalido" }));

    expect(screen.getByTestId("probe").textContent).toContain("BRL|");
    expect(document.cookie).toContain("forja_currency=BRL");
  });
});

function InvalidSetterProbe() {
  const { currency, rates, setCurrency } = useCurrency();
  return (
    <div>
      <span data-testid="probe">{`${currency}|${formatMoney("100", {
        currency,
        locale: "pt-BR",
        rates,
      })}`}</span>
      <button
        type="button"
        onClick={() => setCurrency("CHF" as unknown as Parameters<typeof setCurrency>[0])}
      >
        Valor invalido
      </button>
    </div>
  );
}
