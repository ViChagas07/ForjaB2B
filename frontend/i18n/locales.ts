/**
 * Configuracao central de locales do Forja B2B.
 *
 * `pt-BR` e o locale padrao. `ar` e RTL. O nome dos arquivos em `messages/`
 * deve corresponder exatamente a estes codigos (ex.: messages/pt-BR.json).
 */

export const locales = [
  "pt-BR",
  "en",
  "zh-CN",
  "ja",
  "ko",
  "ru",
  "es",
  "de",
  "fr",
  "it",
  "ar",
] as const;

export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "pt-BR";

export const rtlLocales: readonly Locale[] = ["ar"];

export const localeLabels: Record<Locale, string> = {
  "pt-BR": "Português (Brasil)",
  en: "English",
  "zh-CN": "中文（简体）",
  ja: "日本語",
  ko: "한국어",
  ru: "Русский",
  es: "Español",
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  ar: "العربية",
};

export const localeFlags: Record<Locale, string> = {
  "pt-BR": "🇧🇷",
  en: "🇬🇧",
  "zh-CN": "🇨🇳",
  ja: "🇯🇵",
  ko: "🇰🇷",
  ru: "🇷🇺",
  es: "🇪🇸",
  de: "🇩🇪",
  fr: "🇫🇷",
  it: "🇮🇹",
  ar: "🇸🇦",
};

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

export function isRtlLocale(locale: string): boolean {
  return (rtlLocales as readonly string[]).includes(locale);
}

/** Direcao de escrita derivada da lista unica `rtlLocales`. */
export function directionForLocale(locale: string): "rtl" | "ltr" {
  return isRtlLocale(locale) ? "rtl" : "ltr";
}
