/**
 * Formatação monetária e de datas da interface.
 *
 * Os valores chegam do backend como string Decimal (nunca float no
 * transporte). `formatMoney` com opções converte um valor em BRL para a moeda
 * de exibição usando as taxas do CurrencyProvider; a multiplicação existe
 * apenas para exibição e o arredondamento fica todo por conta do
 * Intl.NumberFormat.
 *
 * A assinatura antiga `formatMoney(amount, currency, locale)` é mantida para
 * as telas que ainda recebem valores na moeda final (BRL). A próxima fase
 * migra essas telas para a assinatura com opções.
 */

import {
  DEFAULT_CURRENCY,
  normalizeCurrency,
  type CurrencyCode,
  type CurrencyRates,
} from "@/core/domain/currency";

export { DEFAULT_CURRENCY };

const CURRENCY_LOCALES: Record<string, string> = {
  BRL: "pt-BR",
};

const APPROXIMATE_PREFIX = "≈\u00A0";

export interface FormatMoneyOptions {
  currency: CurrencyCode;
  locale: string;
  rates?: CurrencyRates | null;
}

function toFiniteNumber(value: string | number): number | null {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function rawValue(value: string | number): string {
  return typeof value === "string" ? value : String(value);
}

function formatCurrencyValue(
  value: number,
  currency: string,
  locale: string,
  useUiLocale: boolean,
): string {
  const currencyLocale = useUiLocale ? locale : (CURRENCY_LOCALES[currency] ?? locale);
  try {
    return new Intl.NumberFormat(currencyLocale, {
      style: "currency",
      currency,
    }).format(value);
  } catch {
    return `${currency} ${value}`;
  }
}

export function formatMoney(amount: string | number, options: FormatMoneyOptions): string;
export function formatMoney(amount: string, currency: string, locale: string): string;
export function formatMoney(
  amount: string | number,
  optionsOrCurrency: FormatMoneyOptions | string,
  locale?: string,
): string {
  const value = toFiniteNumber(amount);
  if (value === null) {
    return rawValue(amount);
  }

  if (typeof optionsOrCurrency === "string") {
    return formatCurrencyValue(value, optionsOrCurrency, locale ?? "pt-BR", false);
  }

  const target = normalizeCurrency(optionsOrCurrency.currency);
  if (target === DEFAULT_CURRENCY) {
    return formatCurrencyValue(value, DEFAULT_CURRENCY, optionsOrCurrency.locale, true);
  }

  const rawRate = optionsOrCurrency.rates?.[target];
  const rate = rawRate === undefined ? null : toFiniteNumber(rawRate);
  if (rate === null || rate <= 0) {
    return formatCurrencyValue(value, DEFAULT_CURRENCY, optionsOrCurrency.locale, true);
  }

  const converted = value * rate;
  return `${APPROXIMATE_PREFIX}${formatCurrencyValue(
    converted,
    target,
    optionsOrCurrency.locale,
    false,
  )}`;
}

/** Sempre BRL, sem o prefixo de aproximação. */
export function formatBrl(amount: string | number, locale: string): string {
  const value = toFiniteNumber(amount);
  if (value === null) {
    return rawValue(amount);
  }
  return formatCurrencyValue(value, DEFAULT_CURRENCY, locale, true);
}

/** Data de referência da taxa (YYYY-MM-DD), sem deslocamento de fuso. */
export function formatRateDate(rateDate: string | null | undefined, locale: string): string {
  if (!rateDate) return "";
  const date = new Date(`${rateDate}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "medium",
      timeZone: "UTC",
    }).format(date);
  } catch {
    return rateDate;
  }
}

/** Nome localizado da moeda; nunca traduzir manualmente. */
export function getCurrencyDisplayName(currency: string, locale: string): string {
  const normalized = normalizeCurrency(currency);
  try {
    return new Intl.DisplayNames([locale], { type: "currency" }).of(normalized) ?? normalized;
  } catch {
    return normalized;
  }
}

/** Simbolo compacto da moeda (ex.: R$, $, EUR) no locale da UI. */
export function getCurrencySymbol(currency: string, locale: string): string {
  const normalized = normalizeCurrency(currency);
  try {
    const parts = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalized,
      currencyDisplay: "narrowSymbol",
    }).formatToParts(1);
    return parts.find((part) => part.type === "currency")?.value ?? normalized;
  } catch {
    return normalized;
  }
}

/**
 * Exemplo de taxa unitaria: `1 USD ≈ R$ 5,43`.
 *
 * A taxa do backend e BRL -> moeda; para mostrar quantos reais valem 1
 * unidade da moeda, inverte-se apenas para exibicao.
 */
export function formatUnitRateInBrl(
  currency: string,
  rates: CurrencyRates | null | undefined,
  locale: string,
): string | null {
  const normalized = normalizeCurrency(currency);
  if (normalized === DEFAULT_CURRENCY) return null;
  const rawRate = rates?.[normalized];
  const rate = rawRate === undefined ? null : toFiniteNumber(rawRate);
  if (rate === null || rate <= 0) return null;
  return `1 ${normalized} ≈ ${formatBrl(1 / rate, locale)}`;
}

export function formatNumber(value: number, locale: string): string {
  try {
    return new Intl.NumberFormat(locale).format(value);
  } catch {
    return String(value);
  }
}

export function formatDate(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  try {
    return new Intl.DateTimeFormat(locale, {
      dateStyle: "short",
      timeStyle: "short",
    }).format(date);
  } catch {
    return value;
  }
}
