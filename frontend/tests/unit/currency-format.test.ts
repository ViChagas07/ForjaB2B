import { describe, expect, it } from "vitest";

import {
  BRL_ONLY_RATES,
  buildCurrencyBootstrap,
  effectiveCurrency,
  normalizeCurrency,
  normalizeFxRatesPayload,
  type FxRatesSnapshot,
} from "@/core/domain/currency";
import { formatBrl, formatMoney, formatRateDate, getCurrencyDisplayName } from "@/shared/lib/money";

const RATES = {
  BRL: "1",
  USD: "0.18408",
  EUR: "0.16477",
  GBP: "0.13738",
  CAD: "0.25713",
  AUD: "0.26204",
  JPY: "28.946",
  CNY: "1.2246",
} as const;

const SNAPSHOT: FxRatesSnapshot = {
  rates: RATES,
  rateDate: "2026-10-30",
  source: "Frankfurter / European Central Bank",
  stale: false,
};

describe("lista fechada e fallback", () => {
  it("aceita somente as oito moedas e cai em BRL para qualquer outro valor", () => {
    expect(normalizeCurrency(" usd ")).toBe("USD");
    expect(normalizeCurrency("JPY")).toBe("JPY");
    expect(normalizeCurrency("CHF")).toBe("BRL");
    expect(normalizeCurrency("")).toBe("BRL");
    expect(normalizeCurrency(null)).toBe("BRL");
    expect(normalizeCurrency(undefined)).toBe("BRL");
  });

  it("moeda sem taxa cai em BRL", () => {
    expect(effectiveCurrency("USD", BRL_ONLY_RATES)).toBe("BRL");
    expect(effectiveCurrency("USD", { BRL: "1", USD: "0" })).toBe("BRL");
    expect(effectiveCurrency("USD", { BRL: "1", USD: "0.18" })).toBe("USD");
  });

  it("cookie invalido ou taxa ausente produz bootstrap em BRL", () => {
    expect(buildCurrencyBootstrap("CHF", SNAPSHOT).currency).toBe("BRL");
    const withoutUsd = buildCurrencyBootstrap("USD", {
      ...SNAPSHOT,
      rates: { BRL: "1", EUR: "0.16" },
    });
    expect(withoutUsd.currency).toBe("BRL");
    expect(withoutUsd.rateDate).toBe("2026-10-30");
    expect(buildCurrencyBootstrap("USD", null)).toEqual({
      currency: "BRL",
      rates: BRL_ONLY_RATES,
      rateDate: null,
      source: null,
      stale: false,
    });
  });
});

describe("parser da resposta do backend", () => {
  it("filtra moedas fora da lista fechada e aceita rates numericos", () => {
    const parsed = normalizeFxRatesPayload({
      base: "BRL",
      rates: { ...RATES, CHF: "0.15", USD: 0.18408 },
      rate_date: "2026-10-30",
      fetched_at: "2026-10-30T23:00:00Z",
      source: "Frankfurter / European Central Bank",
      stale: false,
    });

    expect(parsed).not.toBeNull();
    expect(parsed?.rates).not.toHaveProperty("CHF");
    expect(parsed?.rates.USD).toBe("0.18408");
    expect(parsed?.rateDate).toBe("2026-10-30");
    expect(parsed?.source).toBe("Frankfurter / European Central Bank");
    expect(parsed?.stale).toBe(false);
  });

  it("ignora taxas invalidas e rejeita payload de outra base", () => {
    const parsed = normalizeFxRatesPayload({
      base: "BRL",
      rates: { BRL: "1", USD: "-1", EUR: "0.16" },
      rate_date: "2026-10-30",
      source: "x",
      stale: true,
    });
    expect(parsed?.rates.USD).toBeUndefined();
    expect(parsed?.rates.EUR).toBe("0.16");
    expect(parsed?.stale).toBe(true);

    expect(normalizeFxRatesPayload({ base: "EUR", rates: { USD: "1" } })).toBeNull();
    expect(normalizeFxRatesPayload(null)).toBeNull();
    expect(normalizeFxRatesPayload("x")).toBeNull();
  });
});

describe("formatMoney com conversao para exibicao", () => {
  it("pt-BR converte e prefixa o valor aproximado", () => {
    const formatted = formatMoney("100", { currency: "USD", locale: "pt-BR", rates: RATES });
    expect(formatted.startsWith("≈")).toBe(true);
    expect(formatted).toContain("18,41");
    expect(formatted).toContain("US$");
    expect(formatted).not.toContain("R$");
  });

  it("en converte mantendo o padrao do locale", () => {
    const formatted = formatMoney("100", { currency: "USD", locale: "en", rates: RATES });
    expect(formatted.startsWith("≈")).toBe(true);
    expect(formatted).toContain("18.41");
    expect(formatted).toContain("$");
  });

  it("ja usa JPY sem casas decimais", () => {
    const formatted = formatMoney("100", { currency: "JPY", locale: "ja", rates: RATES });
    expect(formatted.startsWith("≈")).toBe(true);
    expect(formatted).toContain("2,895");
    expect(formatted).not.toContain(".");
  });

  it("ar formata no locale RTL com os digitos do Intl", () => {
    const formatted = formatMoney("100", { currency: "USD", locale: "ar", rates: RATES });
    expect(formatted.startsWith("≈")).toBe(true);
    expect(formatted).toContain("18.41");
    expect(formatted).toContain("US$");
  });

  it("zh-CN formata no locale chines", () => {
    const formatted = formatMoney("100", { currency: "USD", locale: "zh-CN", rates: RATES });
    expect(formatted.startsWith("≈")).toBe(true);
    expect(formatted).toContain("18.41");
  });

  it("taxa ausente cai em BRL sem prefixo de aproximacao", () => {
    const formatted = formatMoney("100", {
      currency: "USD",
      locale: "pt-BR",
      rates: BRL_ONLY_RATES,
    });
    expect(formatted).toContain("R$");
    expect(formatted).toContain("100,00");
    expect(formatted).not.toContain("≈");
  });

  it("BRL escolhido nao recebe prefixo", () => {
    const formatted = formatMoney("1234.56", { currency: "BRL", locale: "pt-BR", rates: RATES });
    expect(formatted).toContain("1.234,56");
    expect(formatted).not.toContain("≈");
  });

  it("mantem a assinatura antiga (valor ja em BRL) para as telas atuais", () => {
    const formatted = formatMoney("1234.56", "BRL", "pt-BR");
    expect(formatted).toContain("1.234,56");
    expect(formatted).not.toContain("≈");
  });

  it("formatBrl nunca usa o prefixo e respeita o locale da UI", () => {
    expect(formatBrl("1234.56", "pt-BR")).toContain("1.234,56");
    expect(formatBrl("1234.56", "en")).toContain("1,234.56");
    expect(formatBrl("1234.56", "en")).not.toContain("≈");
  });
});

describe("data da taxa e nome da moeda", () => {
  it("formata a data de referencia em UTC, sem voltar um dia", () => {
    expect(formatRateDate("2026-10-30", "en")).toBe("Oct 30, 2026");
    expect(formatRateDate("2026-10-30", "pt-BR")).toContain("30");
    expect(formatRateDate("2026-10-30", "ja")).toContain("2026");
    expect(formatRateDate("2026-10-30", "ar")).toContain("2026");
    expect(formatRateDate(null, "en")).toBe("");
    expect(formatRateDate("invalida", "en")).toBe("");
  });

  it("usa Intl.DisplayNames para o nome da moeda", () => {
    expect(getCurrencyDisplayName("USD", "pt-BR")).toContain("Dólar");
    expect(getCurrencyDisplayName("JPY", "en")).toContain("Japanese Yen");
    expect(getCurrencyDisplayName("CNY", "zh-CN")).toContain("人民币");
    expect(getCurrencyDisplayName("CHF", "en")).toBe("Brazilian Real");
  });
});
