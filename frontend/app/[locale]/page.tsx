import type { Metadata } from "next";
import {
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  CreditCard,
  Headset,
  MapPin,
  PackageCheck,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { BrandStrip } from "@/features/home/brand-strip";
import { FeaturedProducts } from "@/features/home/featured-products";
import { HomeCategories } from "@/features/home/home-categories";
import { Link } from "@/i18n/navigation";
import { SiteFooter } from "@/shared/components/site-footer";
import { SiteHeader } from "@/shared/components/site-header";
import { DEFAULT_CURRENCY, formatMoney, formatNumber } from "@/shared/lib/money";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/utils";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations();
  return { title: t("homeTitle"), description: t("homeDescription") };
}

const CHART_BARS = ["42%", "58%", "36%", "72%", "54%", "86%", "64%"];

export default async function HomePage() {
  const t = await getTranslations();
  const locale = await getLocale();

  const trustItems = [
    { icon: BadgeCheck, label: t("home.trustCnpj") },
    { icon: PackageCheck, label: t("home.trustNational") },
    { icon: ShieldCheck, label: t("home.trustSecure") },
  ];

  const features = [
    {
      icon: CreditCard,
      title: t("home.featureCreditTitle"),
      description: t("home.featureCreditDescription"),
    },
    {
      icon: MapPin,
      title: t("home.featureCoverageTitle"),
      description: t("home.featureCoverageDescription"),
    },
    {
      icon: TrendingUp,
      title: t("home.featurePricingTitle"),
      description: t("home.featurePricingDescription"),
    },
    {
      icon: Headset,
      title: t("home.featureSupportTitle"),
      description: t("home.featureSupportDescription"),
    },
  ];

  return (
    <>
      <SiteHeader />
      <main id="main" className="flex-1">
        <section className="surface-ink amber-glow relative overflow-hidden">
          <div aria-hidden="true" className="soft-grid absolute inset-0 opacity-40" />
          <div
            aria-hidden="true"
            className="absolute end-[-10%] top-[-20%] h-[420px] w-[420px] rounded-full bg-primary/10 blur-3xl"
          />

          <div className="container relative grid gap-14 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-24">
            <div className="animate-rise">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-primary">
                <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-primary" />
                {t("home.eyebrow")}
              </span>

              <h1 className="mt-6 max-w-2xl bg-gradient-to-r from-white via-white to-primary bg-clip-text text-4xl font-black leading-[1.04] tracking-tight text-transparent sm:text-5xl lg:text-6xl">
                {t("homeTitle")}
              </h1>

              <p className="mt-6 max-w-xl text-base leading-relaxed text-white/60">
                {t("homeDescription")}
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button
                  asChild
                  size="lg"
                  className="h-12 rounded-xl px-6 text-sm font-semibold shadow-[0_18px_40px_-18px_rgba(245,158,11,0.75)]"
                >
                  <Link href="/onboarding">
                    {t("home.ctaRequestAccount")}
                    <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
                  </Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="h-12 rounded-xl border-white/15 bg-white/[0.04] px-6 text-sm font-semibold text-white hover:bg-white/10 hover:text-white"
                >
                  <Link href="/catalog">{t("home.ctaExploreCatalog")}</Link>
                </Button>
              </div>

              <ul className="mt-9 flex flex-wrap gap-x-6 gap-y-3">
                {trustItems.map(({ icon: Icon, label }) => (
                  <li
                    key={label}
                    className="inline-flex items-center gap-2 text-xs font-medium text-white/60"
                  >
                    <Icon aria-hidden="true" className="h-4 w-4 text-primary" />
                    {label}
                  </li>
                ))}
              </ul>
            </div>

            <div className="relative mx-auto w-full max-w-md animate-fade-in lg:max-w-none">
              <div
                aria-hidden="true"
                className="absolute inset-6 rounded-[2rem] bg-primary/20 blur-3xl"
              />

              <div className="relative rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-2.5 shadow-2xl backdrop-blur">
                <div className="rounded-3xl border border-white/10 bg-[#101012] p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/60">
                        {t("home.dashboardTitle")}
                      </p>
                      <p className="mt-1 text-sm font-semibold text-white">
                        {t("credit.accountTitle")}
                      </p>
                    </div>
                    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-emerald-400" />
                      {t("home.live")}
                    </span>
                  </div>

                  <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] uppercase tracking-wider text-white/60">
                        {t("credit.title")}
                      </span>
                      <CreditCard aria-hidden="true" className="h-4 w-4 text-primary" />
                    </div>
                    <p className="mt-2 text-2xl font-bold tracking-tight text-white">
                      {formatMoney("50000", DEFAULT_CURRENCY, locale)}
                    </p>
                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
                      <div className="h-full w-[36%] rounded-full bg-primary" />
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[10px] uppercase tracking-wider text-white/60">
                      <span>{t("credit.used")}</span>
                      <span>{formatNumber(36, locale)}%</span>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[9px] font-medium uppercase leading-tight tracking-wider text-white/60">
                          {t("home.openOrders")}
                        </span>
                        <PackageCheck
                          aria-hidden="true"
                          className="h-4 w-4 shrink-0 text-primary"
                        />
                      </div>
                      <p className="mt-2 text-xl font-bold text-white">12</p>
                      <div className="mt-2 flex h-6 items-end gap-1">
                        {CHART_BARS.map((height, index) => (
                          <span
                            key={index}
                            className="w-full rounded-sm bg-primary/70"
                            style={{ height }}
                          />
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[9px] font-medium uppercase leading-tight tracking-wider text-white/60">
                          {t("home.avgSavings")}
                        </span>
                        <TrendingUp
                          aria-hidden="true"
                          className="h-4 w-4 shrink-0 text-emerald-300"
                        />
                      </div>
                      <p className="mt-2 text-xl font-bold text-white">
                        {formatNumber(18.6, locale)}%
                      </p>
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div className="h-full w-[68%] rounded-full bg-emerald-400" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="absolute -bottom-6 start-4 hidden max-w-[260px] rounded-2xl border border-white/10 bg-[#151517] p-3.5 shadow-2xl sm:block">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-400/15 text-emerald-300">
                    <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-white">
                      {t("ordering.statusInvoiced")}
                    </p>
                    <p className="truncate text-[10px] text-white/60">
                      {t("home.invoiceDescription")}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <BrandStrip />

        <section id="solucoes" className="border-b border-border bg-secondary/40">
          <div className="container py-20">
            <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              <div className="max-w-2xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-forge-700 dark:text-forge-300">
                  {t("home.categoriesEyebrow")}
                </p>
                <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
                  {t("home.categoriesTitle")}
                </h2>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
                  {t("home.categoriesDescription")}
                </p>
              </div>
              <Button asChild variant="outline" className="w-fit rounded-xl bg-card">
                <Link href="/catalog">
                  {t("home.categoriesCta")}
                  <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
                </Link>
              </Button>
            </div>

            <div className="mt-10">
              <HomeCategories />
            </div>
          </div>
        </section>

        <section className="bg-background">
          <div className="container py-20">
            <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              <div className="max-w-2xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-forge-700 dark:text-forge-300">
                  {t("home.featuredEyebrow")}
                </p>
                <h2 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
                  {t("home.featuredTitle")}
                </h2>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
                  {t("home.featuredDescription")}
                </p>
              </div>
              <Button asChild variant="outline" className="w-fit rounded-xl bg-card">
                <Link href="/catalog">
                  {t("home.featuredCta")}
                  <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
                </Link>
              </Button>
            </div>

            <div className="mt-10">
              <FeaturedProducts />
            </div>
          </div>
        </section>

        <section id="a-forja" className="border-y border-border bg-card">
          <div className="container grid gap-12 py-20 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-forge-700 dark:text-forge-300">
                {t("home.companyEyebrow")}
              </p>
              <h2 className="mt-3 text-3xl font-black leading-tight tracking-tight sm:text-4xl">
                {t("home.companyTitleA")}{" "}
                <span className="text-forge-700 dark:text-forge-300">
                  {t("home.companyTitleB")}
                </span>
              </h2>
              <p className="mt-5 max-w-xl text-sm leading-relaxed text-muted-foreground">
                {t("home.companyDescription")}
              </p>
              <Button asChild className="mt-8 h-12 rounded-xl px-6">
                <Link href="/onboarding">
                  {t("home.companyCta")}
                  <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
                </Link>
              </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {features.map(({ icon: Icon, title, description }, index) => {
                const featured = index === 0;
                return (
                  <div
                    key={title}
                    className={cn(
                      "rounded-2xl border p-6 transition-transform hover:-translate-y-1",
                      featured
                        ? "border-ink bg-ink text-white shadow-[0_24px_60px_-32px_rgba(10,10,10,0.75)]"
                        : "border-border bg-background",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-11 w-11 items-center justify-center rounded-xl",
                        featured
                          ? "bg-primary text-primary-foreground"
                          : "bg-accent text-accent-foreground",
                      )}
                    >
                      <Icon aria-hidden="true" className="h-5 w-5" />
                    </span>
                    <h3 className="mt-5 text-base font-semibold">{title}</h3>
                    <p
                      className={cn(
                        "mt-2 text-sm leading-relaxed",
                        featured ? "text-white/55" : "text-muted-foreground",
                      )}
                    >
                      {description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="container pb-20 pt-20">
          <div className="relative overflow-hidden rounded-3xl bg-primary px-7 py-12 sm:px-12">
            <div aria-hidden="true" className="amber-grid absolute inset-0 opacity-50" />
            <div
              aria-hidden="true"
              className="absolute end-[-6%] top-[-40%] h-72 w-72 rounded-full bg-white/20 blur-3xl"
            />
            <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-2xl">
                <h2 className="text-3xl font-black leading-tight tracking-tight text-primary-foreground sm:text-4xl">
                  {t("home.finalCtaTitle")}
                </h2>
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-primary-foreground/80">
                  {t("home.finalCtaDescription")}
                </p>
              </div>
              <Button
                asChild
                size="lg"
                className="h-12 w-fit rounded-xl bg-ink px-6 text-white hover:bg-ink/90"
              >
                <Link href="/onboarding">
                  {t("home.finalCtaButton")}
                  <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
