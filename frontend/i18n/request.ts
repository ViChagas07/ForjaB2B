import { getRequestConfig } from "next-intl/server";

import { defaultLocale, isLocale } from "./locales";

/**
 * Carrega as mensagens do locale da requisição (resolvido pelo middleware).
 * Cai para o locale padrão caso o locale resolvido seja inválido.
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = requested && isLocale(requested) ? requested : defaultLocale;

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
