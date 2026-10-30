import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations } from "next-intl/server";

import "@/app/globals.css";
import { buildCurrencyBootstrap } from "@/core/domain/currency";
import { CurrencyProfileSync } from "@/features/currency/currency-profile-sync";
import { getFxRatesForServer } from "@/features/currency/server-rates";
import { directionForLocale, isLocale, locales } from "@/i18n/locales";
import { CURRENCY_COOKIE_NAME, readCurrencyCookieValue } from "@/shared/lib/currency-cookie";
import { Providers } from "@/shared/providers";

interface LocaleLayoutProps {
  children: React.ReactNode;
  params: { locale: string };
}

export async function generateMetadata({ params }: LocaleLayoutProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale });
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

  return {
    metadataBase: new URL(baseUrl),
    title: { default: t("homeTitle"), template: `%s · ${t("appName")}` },
    description: t("homeDescription"),
    alternates: {
      canonical: `/${params.locale}`,
      languages: Object.fromEntries(locales.map((l) => [l, `/${l}`])),
    },
    openGraph: {
      type: "website",
      locale: params.locale,
      url: `/${params.locale}`,
      siteName: t("appName"),
      title: t("homeTitle"),
      description: t("homeDescription"),
    },
    twitter: {
      card: "summary_large_image",
      title: t("homeTitle"),
      description: t("homeDescription"),
    },
    icons: {
      icon: [{ url: "/icon.png", type: "image/png", sizes: "512x512" }],
      apple: [{ url: "/apple-icon.png", type: "image/png", sizes: "512x512" }],
    },
  };
}

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = params;

  if (!isLocale(locale)) {
    notFound();
  }

  const t = await getTranslations({ locale });
  const messages = await getMessages({ locale });
  const dir = directionForLocale(locale);
  const requestedCurrency = readCurrencyCookieValue(cookies().get(CURRENCY_COOKIE_NAME)?.value);
  const fxRates = await getFxRatesForServer();
  const initialCurrency = buildCurrencyBootstrap(requestedCurrency, fxRates);

  return (
    <html lang={locale} dir={dir} suppressHydrationWarning>
      <body className="flex min-h-screen flex-col">
        <a href="#main" className="skip-link">
          {t("skipToContent")}
        </a>
        <NextIntlClientProvider messages={messages}>
          <Providers initialCurrency={initialCurrency}>
            <CurrencyProfileSync />
            {children}
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
