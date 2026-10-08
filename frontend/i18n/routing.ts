import { defineRouting } from "next-intl/routing";

import { defaultLocale, locales } from "./locales";

export const routing = defineRouting({
  locales: [...locales],
  defaultLocale,
  localePrefix: { mode: "always" },
  // Sem detecção por Accept-Language: a raiz sempre resolve para o default
  // (pt-BR), conforme especificado no MEGA-PROMPT.
  localeDetection: false,
});
