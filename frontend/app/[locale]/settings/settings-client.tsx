"use client";

import { useLocale, useTranslations } from "next-intl";
import {
  Check,
  Coins,
  Database,
  Globe2,
  Info,
  Laptop,
  Moon,
  Palette,
  ShieldCheck,
  Sun,
} from "lucide-react";

import { CurrencySettingsSection } from "@/features/currency/currency-settings-section";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { isRtlLocale, localeFlags, localeLabels, locales, type Locale } from "@/i18n/locales";
import { cn } from "@/shared/lib/utils";
import { useAuthStore } from "@/shared/stores/auth-store";
import {
  ACCENTS,
  ACCENT_COLORS,
  useUiStore,
  type Accent,
  type FontSize,
  type Theme,
} from "@/shared/stores/ui-store";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

const THEME_OPTIONS: Array<{ value: Theme; icon: typeof Sun; key: string }> = [
  { value: "dark", icon: Moon, key: "themeDark" },
  { value: "light", icon: Sun, key: "themeLight" },
  { value: "system", icon: Laptop, key: "themeSystem" },
];

const FONT_OPTIONS: Array<{ value: FontSize; key: string }> = [
  { value: "small", key: "fontSmall" },
  { value: "normal", key: "fontNormal" },
  { value: "large", key: "fontLarge" },
];

const NAV = [
  { id: "appearance", icon: Palette, key: "appearance" },
  { id: "language", icon: Globe2, key: "language" },
  { id: "currency", icon: Coins, key: "currency" },
  { id: "privacy", icon: ShieldCheck, key: "privacy" },
  { id: "about", icon: Info, key: "about" },
] as const;

export function SettingsClient() {
  const t = useTranslations("settings");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const authStatus = useAuthStore((state) => state.status);
  const theme = useUiStore((state) => state.theme);
  const accent = useUiStore((state) => state.accent);
  const fontSize = useUiStore((state) => state.fontSize);
  const setTheme = useUiStore((state) => state.setTheme);
  const setAccent = useUiStore((state) => state.setAccent);
  const setFontSize = useUiStore((state) => state.setFontSize);

  if (authStatus === "idle") {
    return <div className="h-96 animate-pulse rounded-2xl bg-muted" />;
  }

  if (authStatus !== "authenticated") {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>{t("loginRequiredTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t("loginRequired")}</p>
          <Button asChild className="w-full">
            <Link href="/login">{t("goToLogin")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  function selectLocale(next: Locale) {
    if (next !== locale) {
      router.replace(pathname, { locale: next });
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
      <nav aria-label={t("navLabel")} className="lg:sticky lg:top-24 lg:self-start">
        <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">
          {t("title")}
        </p>
        <div className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-transparent px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-border hover:bg-muted hover:text-foreground"
              >
                <Icon aria-hidden="true" className="h-4 w-4" />
                {t(item.key)}
              </a>
            );
          })}
        </div>
      </nav>

      <div className="min-w-0 space-y-6">
        <header>
          <h1 className="text-3xl font-black tracking-tight">{t("title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </header>

        <section id="appearance" className="scroll-mt-24 space-y-4">
          <h2 className="text-xl font-bold">{t("appearance")}</h2>
          <Card>
            <CardHeader>
              <CardTitle>{t("theme")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-3 gap-3">
                {THEME_OPTIONS.map((option) => {
                  const Icon = option.icon;
                  const selected = theme === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setTheme(option.value)}
                      aria-pressed={selected}
                      className={cn(
                        "relative flex flex-col items-center gap-2 rounded-xl border-2 px-3 py-4 text-xs font-semibold transition-colors",
                        selected
                          ? "border-primary bg-primary/10 text-foreground"
                          : "border-border bg-card text-muted-foreground hover:border-primary/50",
                      )}
                    >
                      <Icon aria-hidden="true" className="h-6 w-6" />
                      {t(option.key)}
                      {selected ? (
                        <Check
                          aria-hidden="true"
                          className="absolute end-2 top-2 h-4 w-4 text-primary"
                        />
                      ) : null}
                    </button>
                  );
                })}
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold">{t("accent")}</p>
                <div className="flex flex-wrap gap-2">
                  {ACCENTS.map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setAccent(item)}
                      aria-label={t(`accents.${item}`)}
                      aria-pressed={accent === item}
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-full border-2 text-white transition-transform hover:scale-110",
                        accent === item ? "border-foreground" : "border-transparent",
                      )}
                      style={{ background: `hsl(${ACCENT_COLORS[item].primary})` }}
                    >
                      {accent === item ? <Check aria-hidden="true" className="h-4 w-4" /> : null}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold">{t("fontSize")}</p>
                <div className="flex flex-wrap gap-2">
                  {FONT_OPTIONS.map((option) => (
                    <Button
                      key={option.value}
                      type="button"
                      variant={fontSize === option.value ? "default" : "outline"}
                      onClick={() => setFontSize(option.value)}
                      aria-pressed={fontSize === option.value}
                    >
                      {t(option.key)}
                    </Button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <section id="language" className="scroll-mt-24 space-y-4">
          <h2 className="text-xl font-bold">{t("language")}</h2>
          <Card>
            <CardContent className="grid gap-3 p-5 sm:grid-cols-2">
              {locales.map((code) => {
                const selected = code === locale;
                return (
                  <button
                    key={code}
                    type="button"
                    lang={code}
                    dir={isRtlLocale(code) ? "rtl" : undefined}
                    aria-pressed={selected}
                    onClick={() => selectLocale(code)}
                    className={cn(
                      "flex items-center justify-between gap-3 rounded-xl border-2 px-4 py-3 text-sm font-semibold transition-colors",
                      selected
                        ? "border-primary bg-primary/10"
                        : "border-border bg-card hover:border-primary/50",
                    )}
                  >
                    <span className="flex items-center gap-3">
                      <span aria-hidden="true" className="text-base leading-none">
                        {localeFlags[code]}
                      </span>
                      {localeLabels[code]}
                    </span>
                    {selected ? (
                      <Check aria-hidden="true" className="h-4 w-4 text-primary" />
                    ) : null}
                  </button>
                );
              })}
            </CardContent>
          </Card>
        </section>

        <CurrencySettingsSection />

        <section id="privacy" className="scroll-mt-24 space-y-4">
          <h2 className="text-xl font-bold">{t("privacy")}</h2>
          <Card>
            <CardContent className="space-y-4 p-5">
              <p className="text-sm text-muted-foreground">{t("privacyDescription")}</p>
              <div className="flex flex-wrap gap-3">
                <Button asChild variant="outline">
                  <Link href="/privacy">{t("privacyPolicy")}</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/privacy">{t("terms")}</Link>
                </Button>
              </div>
              <div className="rounded-xl border bg-muted/30 p-4">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Database aria-hidden="true" className="h-4 w-4" />
                  {t("dataStoredTitle")}
                </p>
                <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                  <li>â€¢ {t("dataOrders")}</li>
                  <li>â€¢ {t("dataAddresses")}</li>
                  <li>â€¢ {t("dataPreferences")}</li>
                </ul>
              </div>
              <p className="text-xs text-muted-foreground">{t("lgpdNote")}</p>
            </CardContent>
          </Card>
        </section>

        <section id="about" className="scroll-mt-24 space-y-4">
          <h2 className="text-xl font-bold">{t("about")}</h2>
          <Card>
            <CardContent className="space-y-3 p-5 text-sm text-muted-foreground">
              <p className="font-semibold text-foreground">{t("aboutApp")}</p>
              <p>{t("aboutDescription")}</p>
              <Alert variant="info">
                <AlertDescription>{t("portfolioNote")}</AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
