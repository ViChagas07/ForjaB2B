import { normalizeCurrency, type CurrencyCode } from "@/core/domain/currency";

/**
 * Cookie de EXIBIÇÃO lido pelo servidor no layout.
 *
 * Não é HttpOnly de propósito: a troca de moeda acontece no cliente, sem
 * recarregar a página, e o cookie é apenas uma preferência visual. Nenhum
 * valor financeiro ou de sessão é guardado aqui.
 */
export const CURRENCY_COOKIE_NAME = "forja_currency";
export const CURRENCY_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export function readCurrencyCookieValue(value: string | undefined): CurrencyCode {
  return normalizeCurrency(value);
}

export function writeCurrencyCookie(value: string): void {
  if (typeof document === "undefined") return;
  const currency = normalizeCurrency(value);
  document.cookie = [
    `${CURRENCY_COOKIE_NAME}=${currency}`,
    "Path=/",
    `Max-Age=${CURRENCY_COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ].join("; ");
}
