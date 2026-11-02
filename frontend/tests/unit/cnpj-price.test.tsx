// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { buildCurrencyBootstrap } from "@/core/domain/currency";
import { CurrencyProvider } from "@/shared/components/currency-provider";
import { CnpjPrice, CnpjVolumeNotice } from "@/shared/components/cnpj-price";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function renderWithCurrency(ui: ReactNode) {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <CurrencyProvider initial={buildCurrencyBootstrap("BRL", null)}>{ui}</CurrencyProvider>
    </NextIntlClientProvider>,
  );
}

afterEach(cleanup);

describe("CnpjPrice", () => {
  it("mostra preço de tabela riscado, preço final, selo e aviso de volume", () => {
    const { container } = renderWithCurrency(
      <CnpjPrice listAmount="100.00" finalAmount="85.00" percent="15.00" showVolumeHint />,
    );

    const text = container.textContent ?? "";
    expect(text).toContain("CNPJ -15%");
    expect(text).toContain("100,00");
    expect(text).toContain("85,00");
    expect(text).toContain("Compre 30 ou mais unidades e pague 30% menos");
    expect(container.querySelector("s")?.textContent).toContain("100,00");
  });

  it("aplica o selo de 30% quando a API devolve a faixa de volume", () => {
    const { container } = renderWithCurrency(
      <CnpjPrice listAmount="100.00" finalAmount="70.00" percent="30.00" />,
    );

    expect(container.textContent).toContain("CNPJ -30%");
  });

  it("não mostra selo nem aviso para usuário não CNPJ", () => {
    const { container } = renderWithCurrency(
      <CnpjPrice listAmount="100.00" finalAmount="100.00" percent="0.00" showVolumeHint />,
    );

    expect(container.textContent).toContain("100,00");
    expect(container.textContent).not.toContain("CNPJ");
    expect(container.textContent).not.toContain("Compre 30");
    expect(container.querySelector("s")).toBeNull();
  });
});

describe("CnpjVolumeNotice", () => {
  it("mostra quantas unidades faltam para a faixa de 30%", () => {
    const { container } = renderWithCurrency(<CnpjVolumeNotice unitsToVolume={7} />);
    expect(container.textContent).toContain("Faltam 7 unidades para 30% de desconto");
  });

  it("confirma a faixa atingida", () => {
    const { container } = renderWithCurrency(<CnpjVolumeNotice band={30} />);
    expect(container.textContent).toContain("30% de desconto aplicado neste produto");
  });
});
