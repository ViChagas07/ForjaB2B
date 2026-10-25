"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import type { SortField, SortOrder } from "@/core/domain/catalog";
import { SORT_FIELDS, SORT_ORDERS } from "@/core/domain/catalog";
import { errorMessageKey } from "@/shared/lib/api-error";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

import { CatalogFilters } from "./catalog-filters";
import { useBrands, useCategories, useProducts } from "./hooks";
import { ProductCard } from "./product-card";

const PAGE_SIZE = 20;

function parseEnum<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : undefined;
}

export function CatalogBrowser() {
  const t = useTranslations();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Estado derivado da URL (fonte de verdade para filtros/paginacao).
  const search = searchParams.get("q") ?? "";
  const categoryId = searchParams.get("category_id") ?? "";
  const brandId = searchParams.get("brand_id") ?? "";
  const sort = parseEnum<SortField>(searchParams.get("sort"), SORT_FIELDS) ?? "name";
  const order = parseEnum<SortOrder>(searchParams.get("order"), SORT_ORDERS) ?? "asc";
  const page = Math.max(1, Number(searchParams.get("page")) || 1);

  const categoriesQuery = useCategories();
  const brandsQuery = useBrands();
  const productsQuery = useProducts({
    q: search || undefined,
    category_id: categoryId || undefined,
    brand_id: brandId || undefined,
    sort,
    order,
    page,
    page_size: PAGE_SIZE,
  });

  function setParam(key: string, value: string | undefined, resetPage = true) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    if (resetPage && key !== "page") {
      params.delete("page");
    }
    router.replace(`${pathname}?${params.toString()}`);
  }

  const products = productsQuery.data?.items ?? [];
  const total = productsQuery.data?.total ?? 0;
  const pages = productsQuery.data?.pages ?? 1;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-forge-700 dark:text-forge-300">
            {t("home.categoriesEyebrow")}
          </p>
          <h1 className="mt-2 text-4xl font-black tracking-tight sm:text-5xl">
            {t("catalog.title")}
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
            {t("home.categoriesDescription")}
          </p>
        </div>
        <span
          data-testid="catalog-results-count"
          className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-muted-foreground shadow-sm"
        >
          <span className="h-2 w-2 rounded-full bg-primary" />
          {t("catalog.results", { count: total })}
        </span>
      </div>

      <CatalogFilters
        search={search}
        categoryId={categoryId}
        brandId={brandId}
        sort={sort}
        order={order}
        categories={categoriesQuery.data}
        brands={brandsQuery.data}
        onSearchChange={(value) => setParam("q", value)}
        onCategoryChange={(value) => setParam("category_id", value)}
        onBrandChange={(value) => setParam("brand_id", value)}
        onSortChange={(value) => setParam("sort", value)}
        onOrderToggle={() => setParam("order", order === "asc" ? "desc" : "asc")}
      />

      {productsQuery.isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-[420px] w-full rounded-2xl" />
          ))}
        </div>
      ) : productsQuery.isError ? (
        <Alert variant="destructive">
          <AlertTitle>{t("catalog.loadError")}</AlertTitle>
          <AlertDescription>{t(errorMessageKey(productsQuery.error))}</AlertDescription>
        </Alert>
      ) : products.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">{t("catalog.noResults")}</p>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}

      {pages > 1 ? (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-card px-5 py-4">
          <Button
            variant="outline"
            size="sm"
            className="rounded-lg"
            disabled={page <= 1}
            onClick={() => setParam("page", String(page - 1), false)}
          >
            {t("catalog.previous")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t("catalog.pageInfo", { page, pages })}
          </span>
          <Button
            variant="outline"
            size="sm"
            className="rounded-lg"
            disabled={page >= pages}
            onClick={() => setParam("page", String(page + 1), false)}
          >
            {t("catalog.next")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
