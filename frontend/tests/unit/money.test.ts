import { describe, expect, it } from "vitest";

import { formatMoney } from "@/shared/lib/money";

describe("formatMoney", () => {
  it("formata BRL como moeda", () => {
    expect(formatMoney("1234.56", "BRL", "pt-BR")).toContain("1.234,56");
  });

  it.each([
    ["4.90", "4,90"],
    ["29.90", "29,90"],
    ["249.90", "249,90"],
    ["3499.90", "3.499,90"],
  ])("formata o preco de referencia %s como R$ %s", (amount, expected) => {
    const formatted = formatMoney(amount, "BRL", "pt-BR");
    expect(formatted).toContain("R$");
    expect(formatted).toContain(expected);
  });

  it("retorna o valor bruto quando não é numérico", () => {
    expect(formatMoney("não-numérico", "BRL", "pt-BR")).toBe("não-numérico");
  });

  it("formata moeda não mapeada passando o código pelo Intl", () => {
    expect(formatMoney("10", "XYZ", "en")).toContain("10.00");
  });
});
