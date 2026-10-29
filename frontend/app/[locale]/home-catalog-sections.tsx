import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { prefetchHomeCatalog } from "@/features/catalog/server-prefetch";
import { BrandStrip } from "@/features/home/brand-strip";
import { FeaturedProducts } from "@/features/home/featured-products";
import { HOME_FEATURED_POOL_SIZE } from "@/features/home/featured-products-constants";
import { HomeCategories } from "@/features/home/home-categories";
import { Link } from "@/i18n/navigation";
import { getQueryClient } from "@/shared/lib/query-client";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

/**
 * Bloco assíncrono da home: o hero continua estático/streaming e só estas
 * seções esperam o prefetch público. O fallback fica visível enquanto o
 * backend responde (inclusive no cold start).
 */
export async function HomeCatalogSections({ locale }: { locale: string }) {
  const t = await getTranslations({ locale });
  const queryClient = getQueryClient();
  await prefetchHomeCatalog(queryClient, locale, HOME_FEATURED_POOL_SIZE);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
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
    </HydrationBoundary>
  );
}

export function HomeCatalogSkeleton() {
  return (
    <div aria-busy="true">
      <div className="border-b border-border bg-card">
        <div className="container flex flex-wrap items-center justify-between gap-5 py-9">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-5 w-72 max-w-full" />
        </div>
      </div>

      <section className="border-b border-border bg-secondary/40">
        <div className="container space-y-8 py-20">
          <div className="space-y-3">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-9 w-72 max-w-full" />
            <Skeleton className="h-4 w-full max-w-xl" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-44 rounded-2xl" />
            ))}
          </div>
        </div>
      </section>

      <section className="bg-background">
        <div className="container space-y-8 py-20">
          <div className="space-y-3">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-9 w-80 max-w-full" />
            <Skeleton className="h-4 w-full max-w-xl" />
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-[420px] rounded-2xl" />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
