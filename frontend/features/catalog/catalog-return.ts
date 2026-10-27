import { locales } from "@/i18n/locales";

const STORAGE_KEY = "forja:catalog-return-url";

function stripLocalePrefix(path: string): string {
  for (const locale of locales) {
    if (path === `/${locale}`) {
      return "/";
    }
    if (path.startsWith(`/${locale}/`)) {
      return path.slice(locale.length + 1);
    }
  }
  return path;
}

export function saveCatalogReturn(url: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(STORAGE_KEY, stripLocalePrefix(url));
  } catch {
    return;
  }
}

export function readCatalogReturn(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const value = window.sessionStorage.getItem(STORAGE_KEY);
    return value && value.startsWith("/catalog") ? value : null;
  } catch {
    return null;
  }
}
