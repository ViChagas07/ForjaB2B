"use client";

import { ArrowDownWideNarrow, Search } from "lucide-react";
import { useTranslations } from "next-intl";

import type { BrandRef, Category, SortField, SortOrder } from "@/core/domain/catalog";
import { SORT_FIELDS } from "@/core/domain/catalog";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

interface CatalogFiltersProps {
  search: string;
  categoryId: string;
  brandId: string;
  sort: SortField;
  order: SortOrder;
  categories: Category[] | undefined;
  brands: BrandRef[] | undefined;
  onSearchChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onBrandChange: (value: string) => void;
  onSortChange: (value: SortField) => void;
  onOrderToggle: () => void;
}

const selectClass =
  "flex h-11 w-full rounded-xl border border-input bg-card px-3 text-sm text-foreground shadow-none transition-colors focus-visible:outline-none focus-visible:border-primary/60 focus-visible:ring-2 focus-visible:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-50";

export function CatalogFilters({
  search,
  categoryId,
  brandId,
  sort,
  order,
  categories,
  brands,
  onSearchChange,
  onCategoryChange,
  onBrandChange,
  onSortChange,
  onOrderToggle,
}: CatalogFiltersProps) {
  const t = useTranslations();

  const sortLabelKeys: Record<SortField, string> = {
    name: "catalog.sortName",
    sku: "catalog.sortSku",
    base_unit_price: "catalog.sortPrice",
    created_at: "catalog.sortNewest",
  };

  return (
    <div className="grid gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
      <div className="space-y-1.5 sm:col-span-2">
        <Label htmlFor="catalog-search" className="text-xs font-medium text-muted-foreground">
          {t("catalog.searchPlaceholder")}
        </Label>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="catalog-search"
            type="search"
            value={search}
            placeholder={t("catalog.searchPlaceholder")}
            onChange={(event) => onSearchChange(event.target.value)}
            className="h-11 rounded-xl bg-card ps-9 shadow-none"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-category" className="text-xs font-medium text-muted-foreground">
          {t("catalog.filterCategory")}
        </Label>
        <select
          id="catalog-category"
          className={selectClass}
          value={categoryId}
          onChange={(event) => onCategoryChange(event.target.value)}
        >
          <option value="">{t("catalog.allCategories")}</option>
          {(categories ?? []).map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-brand" className="text-xs font-medium text-muted-foreground">
          {t("catalog.filterBrand")}
        </Label>
        <select
          id="catalog-brand"
          className={selectClass}
          value={brandId}
          onChange={(event) => onBrandChange(event.target.value)}
        >
          <option value="">{t("catalog.allBrands")}</option>
          {(brands ?? []).map((brand) => (
            <option key={brand.id} value={brand.id}>
              {brand.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-sort" className="text-xs font-medium text-muted-foreground">
          {t("catalog.sortLabel")}
        </Label>
        <select
          id="catalog-sort"
          className={selectClass}
          value={sort}
          onChange={(event) => onSortChange(event.target.value as SortField)}
        >
          {SORT_FIELDS.map((field) => (
            <option key={field} value={field}>
              {t(sortLabelKeys[field])}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="catalog-order" className="text-xs font-medium text-muted-foreground">
          {t("catalog.sortDirection")}
        </Label>
        <button
          id="catalog-order"
          type="button"
          className={`${selectClass} items-center justify-between gap-2`}
          onClick={onOrderToggle}
        >
          <span>{order === "asc" ? t("catalog.sortAsc") : t("catalog.sortDesc")}</span>
          <ArrowDownWideNarrow
            aria-hidden="true"
            className={`h-4 w-4 text-muted-foreground transition-transform ${
              order === "asc" ? "rotate-180" : ""
            }`}
          />
        </button>
      </div>
    </div>
  );
}
