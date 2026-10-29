"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import type { ProductSummary } from "@/core/domain/catalog";
import { ProductCard, useProducts } from "@/features/catalog";
import { Link } from "@/i18n/navigation";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

import { HOME_FEATURED_POOL_SIZE } from "./featured-products-constants";
import { randomSample } from "./random-sample";

const FEATURED_COUNT = 4;

export function FeaturedProducts() {
  const t = useTranslations();
  const query = useProducts({ page_size: HOME_FEATURED_POOL_SIZE });
  const pool = React.useMemo(() => query.data?.items ?? [], [query.data]);
  const [products, setProducts] = React.useState<ProductSummary[]>([]);

  const reshuffle = React.useCallback(() => {
    setProducts(randomSample(pool, FEATURED_COUNT));
  }, [pool]);

  React.useEffect(() => {
    reshuffle();
  }, [reshuffle]);

  React.useEffect(() => {
    function handleVisibility() {
      if (document.visibilityState === "visible") {
        reshuffle();
      }
    }
    function handlePageShow(event: PageTransitionEvent) {
      if (event.persisted) {
        reshuffle();
      }
    }
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("pageshow", handlePageShow);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("pageshow", handlePageShow);
    };
  }, [reshuffle]);

  if (query.isLoading) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-[420px] rounded-2xl" />
        ))}
      </div>
    );
  }

  if (query.isError || pool.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center">
        <p className="text-sm text-muted-foreground">{t("home.featuredEmpty")}</p>
        <Button asChild variant="outline" className="mt-5 rounded-xl">
          <Link href="/catalog">{t("home.featuredCta")}</Link>
        </Button>
      </div>
    );
  }

  const visible = products.length > 0 ? products : randomSample(pool, FEATURED_COUNT);

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {visible.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
