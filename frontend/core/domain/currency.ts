/**
 * Moedas de EXIBIÇÃO aceitas pela interface.
 *
 * A lista é fechada e a base é sempre BRL. O backend continua calculando tudo
 * em reais; as taxas aqui servem apenas para aproximar o valor mostrado. Uma
 * moeda desconhecida (cookie adulterado, query, perfil antigo) sempre cai em
 * BRL.
 */

export const SUPPORTED_CURRENCIES = [
  "BRL",
  "USD",
  "EUR",
  "GBP",
  "CAD",
  "AUD",
  "JPY",
  "CNY",
] as const;

export type CurrencyCode = (typeof SUPPORTED_CURRENCIES)[number];

export const DEFAULT_CURRENCY: CurrencyCode = "BRL";

export const QUOTE_CURRENCIES = SUPPORTED_CURRENCIES.filter(
  (currency): currency is Exclude<CurrencyCode, "BRL"> => currency !== "BRL",
);

/** Taxas ausentes não impedem a renderização: BRL continua disponível. */
export type CurrencyRates = Readonly<Partial<Record<CurrencyCode, string>>>;

export const BRL_ONLY_RATES: CurrencyRates = Object.freeze({ BRL: "1" });

export interface FxRatesSnapshot {
  rates: CurrencyRates;
  rateDate: string | null;
  source: string | null;
  stale: boolean;
}

export interface CurrencyBootstrap extends FxRatesSnapshot {
  currency: CurrencyCode;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isSupportedCurrency(value: string | null | undefined): value is CurrencyCode {
  if (typeof value !== "string") return false;
  return (SUPPORTED_CURRENCIES as readonly string[]).includes(value.trim().toUpperCase());
}

/** Moeda válida ou BRL (nunca lança; usado em cookie/query). */
export function normalizeCurrency(value: string | null | undefined): CurrencyCode {
  if (!isSupportedCurrency(value)) return DEFAULT_CURRENCY;
  return value.trim().toUpperCase() as CurrencyCode;
}

/**
 * Moeda realmente exibível: a escolhida, desde que a taxa exista; senão BRL.
 */
export function effectiveCurrency(
  requested: string | null | undefined,
  rates: CurrencyRates,
): CurrencyCode {
  const normalized = normalizeCurrency(requested);
  if (normalized === DEFAULT_CURRENCY) return DEFAULT_CURRENCY;
  const rate = rates[normalized];
  if (rate === undefined) return DEFAULT_CURRENCY;
  const numeric = Number(rate);
  return Number.isFinite(numeric) && numeric > 0 ? normalized : DEFAULT_CURRENCY;
}

/**
 * Converte a resposta de `/api/v1/fx/rates` para o contrato da UI.
 *
 * O parser é deliberadamente tolerante: ignora moedas fora da lista fechada,
 * taxas inválidas e campos ausentes. Quem decide o fallback final é
 * `buildCurrencyBootstrap`.
 */
export function normalizeFxRatesPayload(payload: unknown): FxRatesSnapshot | null {
  if (!isRecord(payload) || payload.base !== "BRL" || !isRecord(payload.rates)) {
    return null;
  }

  const rates: Partial<Record<CurrencyCode, string>> = { BRL: "1" };
  for (const currency of QUOTE_CURRENCIES) {
    const raw = payload.rates[currency];
    if (typeof raw !== "string" && typeof raw !== "number") continue;
    const numeric = Number(raw);
    if (!Number.isFinite(numeric) || numeric <= 0) continue;
    rates[currency] = typeof raw === "string" ? raw.trim() : String(raw);
  }

  const rawDate = payload.rate_date;
  const rateDate =
    typeof rawDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(rawDate) ? rawDate : null;
  const rawSource = payload.source;
  const source = typeof rawSource === "string" && rawSource.trim() ? rawSource.trim() : null;

  return {
    rates,
    rateDate,
    source,
    stale: payload.stale === true,
  };
}

/** Estado inicial determinístico do provider (servidor e cliente). */
export function buildCurrencyBootstrap(
  requested: string | null | undefined,
  snapshot: FxRatesSnapshot | null,
): CurrencyBootstrap {
  const rates = snapshot?.rates ?? BRL_ONLY_RATES;
  return {
    currency: effectiveCurrency(requested, rates),
    rates,
    rateDate: snapshot?.rateDate ?? null,
    source: snapshot?.source ?? null,
    stale: snapshot?.stale ?? false,
  };
}
