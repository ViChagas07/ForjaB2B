// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { buildCurrencyBootstrap, type FxRatesSnapshot } from "@/core/domain/currency";
import { CurrencySettingsSection } from "@/features/currency/currency-settings-section";
import { CurrencyProvider } from "@/shared/components/currency-provider";

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

function renderSection(snapshot: FxRatesSnapshot = SNAPSHOT, requested = "BRL") {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <CurrencyProvider initial={buildCurrencyBootstrap(requested, snapshot)}>
        <CurrencySettingsSection />
      </CurrencyProvider>
    </NextIntlClientProvider>,
  );
}

function radio(name: RegExp): HTMLButtonElement {
  return screen.getByRole("radio", { name }) as HTMLButtonElement;
}

afterEach(() => {
  cleanup();
  document.cookie = "forja_currency=; Max-Age=0; Path=/";
});

describe("CurrencySettingsSection", () => {
  it("lista as oito moedas com nome localizado e seleciona BRL por padrão", () => {
    renderSection();

    expect(screen.getAllByRole("radio")).toHaveLength(8);
    expect(radio(/BRL/).getAttribute("aria-checked")).toBe("true");
    expect(radio(/USD/).getAttribute("aria-checked")).toBe("false");
    expect(radio(/USD/).textContent).toContain("Dólar americano");
    expect(screen.getByText(/Frankfurter \/ European Central Bank/)).toBeTruthy();
    expect(screen.getByText(/30 de out. de 2026/)).toBeTruthy();
  });

  it("troca a moeda, atualiza o exemplo de taxa e persiste no cookie", () => {
    renderSection();

    fireEvent.click(radio(/USD/));

    expect(radio(/USD/).getAttribute("aria-checked")).toBe("true");
    expect(document.cookie).toContain("forja_currency=USD");
    expect(screen.getByText(/1 USD ≈ R\$\s*5,43/)).toBeTruthy();
    expect(screen.queryByText(/1 USD ≈ R\$\s*5,43/)).not.toBeNull();
  });

  it("navega pelo radiogroup com as setas", () => {
    renderSection();

    fireEvent.click(radio(/USD/));
    const usd = radio(/USD/);
    usd.focus();
    fireEvent.keyDown(usd, { key: "ArrowRight" });

    expect(radio(/EUR/).getAttribute("aria-checked")).toBe("true");
    expect(document.cookie).toContain("forja_currency=EUR");
  });

  it("desabilita opções sem taxa e informa indisponibilidade", () => {
    renderSection(
      {
        rates: { BRL: "1" },
        rateDate: null,
        source: null,
        stale: false,
      },
      "USD",
    );

    expect(radio(/BRL/).getAttribute("aria-checked")).toBe("true");
    expect(radio(/USD/).disabled).toBe(true);
    expect(radio(/EUR/).disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toContain("Conversão indisponível");
  });

  it("mostra aviso discreto quando a taxa está stale", () => {
    renderSection({ ...SNAPSHOT, stale: true }, "USD");

    expect(screen.getByText(/A taxa pode estar desatualizada/)).toBeTruthy();
  });
});
