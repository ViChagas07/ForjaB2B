"use client";

import { useTranslations } from "next-intl";

import { ProductCard, useProducts } from "@/features/catalog";
import { Link } from "@/i18n/navigation";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

export function FeaturedProducts() {
  const t = useTranslations();
  const query = useProducts({ page_size: 4, sort: "created_at", order: "desc" });
  const products = query.data?.items ?? [];

  if (query.isLoading) {
    return (
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-[420px] rounded-2xl" />
        ))}
      </div>
    );
  }

  if (query.isError || products.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-card p-10 text-center">
        <p className="text-sm text-muted-foreground">{t("home.featuredEmpty")}</p>
        <Button asChild variant="outline" className="mt-5 rounded-xl">
          <Link href="/catalog">{t("home.featuredCta")}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
