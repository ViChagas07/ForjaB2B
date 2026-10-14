import { defineRouting } from "next-intl/routing";

import { defaultLocale, locales } from "./locales";

export const routing = defineRouting({
  locales: [...locales],
  defaultLocale,
  localePrefix: { mode: "always" },
  // Detecção de locale pelo Accept-Language do navegador na primeira visita
  localeDetection: true,
});
