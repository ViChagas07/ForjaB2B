"use client";

import { useTranslations } from "next-intl";

import { useBrands } from "@/features/catalog";
import { Skeleton } from "@/shared/ui/skeleton";

export function BrandStrip() {
  const t = useTranslations();
  const query = useBrands();

  const brands = query.data ?? [];

  if (!query.isLoading && brands.length === 0) {
    return null;
  }

  return (
    <section aria-labelledby="brands-title" className="border-b border-border bg-card">
      <div className="container grid gap-6 py-9 md:grid-cols-[220px_1fr] md:items-center">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-forge-700 dark:text-forge-300">
            {t("home.brandsEyebrow")}
          </p>
          <h2 id="brands-title" className="mt-1 text-sm font-medium text-foreground">
            {t("home.brandsTitle")}
          </h2>
        </div>

        <div className="flex flex-wrap items-center justify-start gap-x-10 gap-y-5 md:justify-end">
          {query.isLoading
            ? Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-5 w-24" />
              ))
            : brands.slice(0, 6).map((brand) => (
                <span
                  key={brand.id}
                  className="text-base font-bold uppercase tracking-[0.18em] text-foreground/60 transition-colors hover:text-foreground/70"
                >
                  {brand.name}
                </span>
              ))}
        </div>
      </div>
    </section>
  );
}
