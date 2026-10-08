"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import type { SortField, SortOrder } from "@/core/domain/catalog";
import { SORT_FIELDS, SORT_ORDERS } from "@/core/domain/catalog";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import { errorMessageKey } from "@/shared/lib/api-error";

import { useBrands, useCategories, useProducts } from "./hooks";
import { CatalogFilters } from "./catalog-filters";
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("catalog.title")}</h1>
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

      {search ? (
        <p className="text-sm text-muted-foreground" data-testid="catalog-results-count">
          {t("catalog.results", { count: total })}
        </p>
      ) : null}

      {productsQuery.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-56 w-full" />
          ))}
        </div>
      ) : productsQuery.isError ? (
        <Alert variant="destructive">
          <AlertTitle>{t("catalog.loadError")}</AlertTitle>
          <AlertDescription>{t(errorMessageKey(productsQuery.error))}</AlertDescription>
        </Alert>
      ) : products.length === 0 ? (
        <Alert variant="info">
          <AlertDescription>{t("catalog.noResults")}</AlertDescription>
        </Alert>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      )}

      {pages > 1 ? (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
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
