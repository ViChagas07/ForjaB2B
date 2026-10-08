/**
 * Formatação monetária. Os valores monetários chegam do backend como string
 * (Decimal serializado) — nunca como float — e são formatados aqui sem
 * aritmética de ponto flutuante. O locale de exibição segue o idioma ativo.
 */

const CURRENCY_LOCALES: Record<string, string> = {
  BRL: "pt-BR",
};

/** Moeda padrão do catálogo/pedido (backend Forja B2B). */
export const DEFAULT_CURRENCY = "BRL";

export function formatMoney(amount: string, currency: string, locale: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) {
    return amount;
  }
  const currencyLocale = CURRENCY_LOCALES[currency] ?? locale;
  try {
    return new Intl.NumberFormat(currencyLocale, {
      style: "currency",
      currency,
    }).format(value);
  } catch {
    return `${currency} ${amount}`;
  }
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
