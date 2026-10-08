"use client";

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

  const selectClass =
    "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  const sortLabelKeys: Record<SortField, string> = {
    name: "catalog.sortName",
    sku: "catalog.sortSku",
    base_unit_price: "catalog.sortPrice",
    created_at: "catalog.sortNewest",
  };

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div className="space-y-2 lg:col-span-2">
        <Input
          type="search"
          value={search}
          placeholder={t("catalog.searchPlaceholder")}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="catalog-category">{t("catalog.filterCategory")}</Label>
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

      <div className="space-y-2">
        <Label htmlFor="catalog-brand">{t("catalog.filterBrand")}</Label>
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

      <div className="space-y-2">
        <Label htmlFor="catalog-sort">{t("catalog.sortLabel")}</Label>
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

      <div className="space-y-2">
        <Label>{t("catalog.sortLabel")}</Label>
        <button
          type="button"
          className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm shadow-sm"
          onClick={onOrderToggle}
        >
          {order === "asc" ? t("catalog.sortAsc") : t("catalog.sortDesc")}
        </button>
      </div>
    </div>
  );
}
