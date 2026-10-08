import { describe, expect, it } from "vitest";

import { formatMoney } from "@/shared/lib/money";

describe("formatMoney", () => {
  it("formata BRL como moeda", () => {
    expect(formatMoney("1234.56", "BRL", "pt-BR")).toContain("1.234,56");
  });

  it("retorna o valor bruto quando não é numérico", () => {
    expect(formatMoney("não-numérico", "BRL", "pt-BR")).toBe("não-numérico");
  });

  it("formata moeda não mapeada passando o código pelo Intl", () => {
    expect(formatMoney("10", "XYZ", "en")).toContain("10.00");
  });
});
