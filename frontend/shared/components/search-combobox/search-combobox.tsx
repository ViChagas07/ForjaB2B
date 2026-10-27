"use client";

import * as React from "react";
import { ArrowRight, Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import type { components } from "@/core/domain/api-schema";
import { useSearchSuggestions } from "@/features/search/use-search-suggestions";
import { isRtlLocale } from "@/i18n/locales";
import { Link, useRouter } from "@/i18n/navigation";
import { cn } from "@/shared/lib/utils";
import { Input } from "@/shared/ui/input";
import { Skeleton } from "@/shared/ui/skeleton";

import { ProductPreviewList } from "./product-preview-list";
import { SuggestionList } from "./suggestion-list";

type SuggestTerm = components["schemas"]["SuggestTermOut"];
type SuggestCategory = components["schemas"]["SuggestCategoryOut"];
type SearchProduct = components["schemas"]["SearchProductOut-Output"];

const MIN_QUERY_LENGTH = 2;
/** Blocos de navegação plana: termos | categorias | produtos. */
const BLOCK_TERMS = 0;
const BLOCK_CATEGORIES = 1;
const BLOCK_PRODUCTS = 2;

export interface SearchComboboxProps {
  className?: string;
  inputClassName?: string;
}

/**
 * Barra de busca do header com dropdown estilo BestBuy: termos/categorias à
 * esquerda e até 6 produtos à direita. Combobox ARIA feito à mão (sem
 * dependências): teclado, Esc/Tab/click-fora, classes lógicas (RTL-safe) e
 * preços sempre hidratados do backend (o índice nunca guarda preço).
 */
export function SearchCombobox({ className, inputClassName }: SearchComboboxProps) {
  const t = useTranslations();
  const router = useRouter();
  const locale = useLocale();
  const isRtl = isRtlLocale(locale);

  const [query, setQuery] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState<number | null>(null);

  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const listboxId = React.useId().replace(/[^a-zA-Z0-9_-]/g, "r");

  const suggestions = useSearchSuggestions(query);
  const data = suggestions.data;
  const isFetching = suggestions.isFetching;

  const normalizedQuery = query.trim();
  const hasQuery = normalizedQuery.length >= MIN_QUERY_LENGTH;
  const terms = data?.terms ?? [];
  const categories = data?.categories ?? [];
  const products = data?.products ?? [];
  const termBase = BLOCK_TERMS;
  const categoryBase = terms.length;
  const productBase = categoryBase + categories.length;
  const totalOptions = terms.length + categories.length + products.length;
  const listboxVisible = Boolean(open && hasQuery && (isFetching || data));

  // Option ativo rola para dentro da área visível (navegação por teclado).
  React.useEffect(() => {
    if (activeIndex === null) {
      return;
    }
    document
      .getElementById(`${listboxId}-opt-${activeIndex}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, listboxId]);

  // Clique fora (pointerdown) fecha; limpo no unmount e quando fecha.
  React.useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: PointerEvent): void {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setActiveIndex(null);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Nova resposta: nenhuma opção fica pré-selecionada (comportamento BestBuy).
  React.useEffect(() => {
    setActiveIndex(null);
  }, [data]);

  const go = React.useCallback(
    (href: string) => {
      setOpen(false);
      setActiveIndex(null);
      router.push(href);
    },
    [router],
  );

  const handleTermSelect = React.useCallback(
    (term: SuggestTerm) => go(`/catalog?q=${encodeURIComponent(term.text)}`),
    [go],
  );
  const handleCategorySelect = React.useCallback(
    // O /catalog aceita apenas category_id (uuid) — o suggest traz slug, então
    // a categoria navega pela busca do termo digitado (decisão da fase).
    (category: SuggestCategory) => go(`/catalog?q=${encodeURIComponent(normalizedQuery)}`),
    [go, normalizedQuery],
  );
  const handleProductSelect = React.useCallback(
    (product: SearchProduct) => go(`/catalog/${product.id}`),
    [go],
  );

  function blockBounds(index: number | null): { start: number; end: number } | null {
    if (totalOptions === 0) {
      return null;
    }
    const current = index ?? -1;
    if (current < categoryBase) {
      return { start: termBase, end: categoryBase };
    }
    if (current < productBase) {
      return { start: categoryBase, end: productBase };
    }
    return { start: productBase, end: totalOptions };
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "Escape") {
      // Fecha mantendo o texto digitado.
      setOpen(false);
      setActiveIndex(null);
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      setActiveIndex(null);
      return;
    }
    if (!hasQuery) {
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open || totalOptions === 0) {
        setOpen(true);
        return;
      }
      const delta = event.key === "ArrowDown" ? 1 : -1;
      setActiveIndex((current) => {
        const base = current ?? (delta > 0 ? -1 : totalOptions);
        return Math.min(totalOptions - 1, Math.max(0, base + delta));
      });
      return;
    }
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      if (!open || totalOptions === 0) {
        return;
      }
      const forward = (event.key === "ArrowRight") !== isRtl; // RTL inverte
      const bounds = blockBounds(activeIndex);
      if (bounds === null) {
        return;
      }
      event.preventDefault();
      const next = bounds.start === 0 && bounds.end === totalOptions ? null : bounds;
      if (next === null) {
        setActiveIndex(null);
        return;
      }
      const target = forward ? next.end : next.start - 1;
      setActiveIndex(Math.min(totalOptions - 1, Math.max(0, target)));
      return;
    }
    if (event.key === "Enter" && open && activeIndex !== null) {
      event.preventDefault();
      const current = activeIndex;
      if (current < categoryBase) {
        const term = terms[current];
        if (term) {
          handleTermSelect(term);
        }
      } else if (current < productBase) {
        const category = categories[current - categoryBase];
        if (category) {
          handleCategorySelect(category);
        }
      } else {
        const product = products[current - productBase];
        if (product) {
          handleProductSelect(product);
        }
      }
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    go(normalizedQuery ? `/catalog?q=${encodeURIComponent(normalizedQuery)}` : "/catalog");
  }

  const gridClasses =
    products.length > 0 ? "md:grid md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]" : "";

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      <form role="search" onSubmit={handleSubmit}>
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/60"
        />
        <Input
          type="search"
          value={query}
          role="combobox"
          aria-expanded={listboxVisible}
          aria-controls={listboxVisible ? listboxId : undefined}
          aria-autocomplete="list"
          aria-activedescendant={
            activeIndex !== null ? `${listboxId}-opt-${activeIndex}` : undefined
          }
          aria-label={t("nav.searchLabel")}
          placeholder={t("nav.searchPlaceholder")}
          autoComplete="off"
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            if (hasQuery) {
              setOpen(true);
            }
          }}
          onKeyDown={handleKeyDown}
          className={cn(
            "h-10 rounded-xl border-white/10 bg-white/[0.06] pe-11 ps-9 text-sm text-white shadow-none placeholder:text-white/60 focus-visible:border-primary/50 focus-visible:ring-primary",
            inputClassName,
          )}
        />
        <button
          type="submit"
          aria-label={t("nav.searchSubmit")}
          className="absolute end-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
        >
          <ArrowRight aria-hidden="true" className="h-3.5 w-3.5 rtl:-scale-x-100" />
        </button>
      </form>

      {listboxVisible ? (
        <div
          className={cn(
            "z-40 overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-[0_24px_50px_-24px_rgba(10,10,10,0.4)]",
            "max-md:fixed max-md:inset-x-0 max-md:top-[72px] max-md:rounded-none",
            "md:absolute md:start-0 md:top-full md:mt-2 md:w-[min(52rem,90vw)]",
          )}
        >
          <ul
            id={listboxId}
            role="listbox"
            aria-label={t("nav.searchLabel")}
            className={cn("max-h-[70vh] overflow-y-auto md:max-h-[26rem]", gridClasses)}
          >
            {!data && isFetching ? (
              <li role="presentation" className="p-2">
                <ul className="space-y-1">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <li key={index} className="flex items-center gap-3 rounded-xl px-2 py-2.5">
                      <Skeleton className="h-10 w-10 shrink-0 rounded-lg" />
                      <div className="flex-1 space-y-2">
                        <Skeleton className="h-3 w-2/3" />
                        <Skeleton className="h-3 w-1/3" />
                      </div>
                    </li>
                  ))}
                </ul>
              </li>
            ) : totalOptions === 0 ? (
              <li role="presentation" className="px-4 py-6 text-center">
                <p className="text-sm text-muted-foreground">
                  {t("search.noResults", { q: normalizedQuery })}
                </p>
                <Link
                  href={`/catalog?q=${encodeURIComponent(normalizedQuery)}`}
                  onClick={() => setOpen(false)}
                  className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
                >
                  {t("search.viewAll")}
                  <ArrowRight aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100" />
                </Link>
              </li>
            ) : (
              <>
                <SuggestionList
                  terms={terms}
                  categories={categories}
                  query={normalizedQuery}
                  listboxId={listboxId}
                  baseIndex={termBase}
                  activeIndex={activeIndex}
                  onActiveIndexChange={setActiveIndex}
                  onTermSelect={handleTermSelect}
                  onCategorySelect={handleCategorySelect}
                />
                <ProductPreviewList
                  products={products}
                  query={data?.query ?? normalizedQuery}
                  listboxId={listboxId}
                  baseIndex={productBase}
                  activeIndex={activeIndex}
                  onActiveIndexChange={setActiveIndex}
                  onProductSelect={handleProductSelect}
                />
              </>
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
