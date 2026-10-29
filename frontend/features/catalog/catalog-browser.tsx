"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { useDebouncedValue } from "@/features/search";
import { errorMessageKey } from "@/shared/lib/api-error";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

import { CatalogFilters } from "./catalog-filters";
import { saveCatalogReturn } from "./catalog-return";
import { useBrands, useCategories, useProducts } from "./hooks";
import { ProductCard } from "./product-card";
import { parseCatalogSearchParams } from "./search-params";

/** Debounce do campo de busca do catálogo (ms): 1 request por pausa, não por tecla. */
const SEARCH_DEBOUNCE_MS = 300;

export function CatalogBrowser() {
  const t = useTranslations();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Estado derivado da URL (fonte de verdade para filtros/paginacao). O mesmo
  // parser roda no Server Component para o prefetch usar a mesma query key.
  const { search, categoryId, brandId, sort, order, page, query } = parseCatalogSearchParams(
    Object.fromEntries(searchParams.entries()),
  );

  // Estado local do campo: digitação responsiva; a URL (e a busca) acompanham
  // com debounce, como no combobox do header. Sem isso, cada tecla dispara
  // router.replace + fetch de /catalog/products.
  const [searchInput, setSearchInput] = React.useState(search);
  const debouncedSearch = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS);

  // A URL manda (voltar/avançar, submit do combobox, links): sincroniza o campo.
  React.useEffect(() => {
    setSearchInput(search);
  }, [search]);

  // Atualiza a URL somente quando a digitação pausa (o `setParam` já reseta a
  // página e é estável em comportamento; o sync acima evita valor defasado).
  React.useEffect(() => {
    if (debouncedSearch === search) {
      return;
    }
    setParam("q", debouncedSearch || undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const categoriesQuery = useCategories();
  const brandsQuery = useBrands();
  const productsQuery = useProducts(query);

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

  const [pageJumpOpen, setPageJumpOpen] = React.useState(false);
  const [pageDraft, setPageDraft] = React.useState("");
  const pageJumpRef = React.useRef<HTMLDivElement | null>(null);

  function openPageJump() {
    setPageDraft(String(page));
    setPageJumpOpen(true);
  }

  function submitPageJump(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number.parseInt(pageDraft, 10);
    if (Number.isFinite(value)) {
      const clamped = Math.min(Math.max(value, 1), pages);
      setParam("page", String(clamped), false);
    }
    setPageJumpOpen(false);
  }

  React.useEffect(() => {
    if (!pageJumpOpen) {
      return;
    }
    function handlePointerDown(event: PointerEvent) {
      if (!pageJumpRef.current?.contains(event.target as Node)) {
        setPageJumpOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPageJumpOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [pageJumpOpen]);

  React.useEffect(() => {
    setPageJumpOpen(false);
  }, [page, pages]);

  const currentUrl = `${pathname}?${searchParams.toString()}`;
  React.useEffect(() => {
    saveCatalogReturn(currentUrl);
  }, [currentUrl]);

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
        search={searchInput}
        categoryId={categoryId}
        brandId={brandId}
        sort={sort}
        order={order}
        categories={categoriesQuery.data}
        brands={brandsQuery.data}
        onSearchChange={setSearchInput}
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
          <div ref={pageJumpRef} className="relative">
            {pageJumpOpen ? (
              <div className="absolute inset-x-0 bottom-full z-10 mb-2 flex justify-center">
                <form
                  onSubmit={submitPageJump}
                  noValidate
                  className="flex items-center gap-2 rounded-xl border border-border bg-card p-2 shadow-lg"
                >
                  <label
                    htmlFor="catalog-page-jump"
                    className="text-xs font-medium text-muted-foreground"
                  >
                    {t("catalog.jumpToPage")}
                  </label>
                  <input
                    id="catalog-page-jump"
                    type="number"
                    min={1}
                    max={pages}
                    inputMode="numeric"
                    autoFocus
                    value={pageDraft}
                    onFocus={(event) => event.target.select()}
                    onChange={(event) => setPageDraft(event.target.value)}
                    className="h-9 w-16 rounded-lg border border-input bg-background px-2 text-center text-sm text-foreground shadow-none"
                  />
                  <Button
                    type="submit"
                    size="sm"
                    className="h-9 w-9 rounded-lg p-0"
                    aria-label={t("catalog.jumpToPage")}
                  >
                    <ArrowRight aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100" />
                  </Button>
                </form>
              </div>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              className="rounded-lg text-sm text-muted-foreground hover:text-foreground"
              aria-haspopup="dialog"
              aria-expanded={pageJumpOpen}
              onClick={openPageJump}
            >
              {t("catalog.pageInfo", { page, pages })}
            </Button>
          </div>
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
