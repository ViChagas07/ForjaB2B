"use client";

import { ArrowUpRight, Boxes, Factory, HardHat, ShieldCheck, Wrench, Zap } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { useCategories } from "@/features/catalog";
import { categoryIllustration } from "@/features/home/category-illustrations";
import { displayCategoryName } from "@/shared/lib/category-display";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

const ICONS = [HardHat, Wrench, ShieldCheck, Factory, Boxes, Zap];

export function HomeCategories() {
  const t = useTranslations();
  const query = useCategories();
  const categories = (query.data ?? []).slice(0, 4);

  if (query.isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-44 rounded-2xl" />
        ))}
      </div>
    );
  }

  if (query.isError || categories.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center">
        <p className="text-sm text-muted-foreground">{t("home.categoriesEmpty")}</p>
        <Button asChild className="mt-5 rounded-xl">
          <Link href="/catalog">{t("home.categoriesCta")}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {categories.map((category, index) => {
        const Icon = ICONS[index % ICONS.length] ?? HardHat;
        const name = displayCategoryName(category.name);
        const illustration = categoryIllustration(name);
        return (
          <Link
            key={category.id}
            href={`/catalog?category_id=${category.id}`}
            className="group relative flex h-44 flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card p-5 transition-all hover:-translate-y-1 hover:border-primary/50 hover:shadow-[0_18px_40px_-24px_rgba(10,10,10,0.35)]"
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-accent-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
              <Icon aria-hidden="true" className="h-5 w-5" />
            </span>
            <span>
              <span className="block text-base font-semibold leading-snug">{name}</span>
              <span className="mt-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
                {t("home.categoryExplore")}
                <ArrowUpRight
                  aria-hidden="true"
                  className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 rtl:-scale-x-100"
                />
              </span>
            </span>
            <span className="pointer-events-none absolute end-4 top-4 h-24 w-24 overflow-hidden rounded-full bg-primary/5 transition-transform duration-500 group-hover:scale-150">
              {illustration ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={encodeURI(illustration)}
                  alt=""
                  aria-hidden="true"
                  loading="lazy"
                  decoding="async"
                  onError={(event) => {
                    event.currentTarget.style.visibility = "hidden";
                  }}
                  className="h-full w-full object-cover"
                />
              ) : null}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
