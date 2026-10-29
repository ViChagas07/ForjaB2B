"use client";

import * as React from "react";
import {
  ArrowLeft,
  BadgeCheck,
  BadgePercent,
  CreditCard,
  Minus,
  PackageCheck,
  Plus,
  ShieldCheck,
  Truck,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { AddToCartButton, BuyNowButton } from "@/features/cart";
import { useRouter } from "@/i18n/navigation";
import { isLocale, localeLabels } from "@/i18n/locales";
import { errorMessageKey } from "@/shared/lib/api-error";
import { displayCategoryName } from "@/shared/lib/category-display";
import { formatNumber } from "@/shared/lib/money";
import { ProductImage } from "@/shared/components/product-image";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Skeleton } from "@/shared/ui/skeleton";

import { isPurchasable } from "./availability";
import { CatalogPrice } from "./catalog-price";
import { readCatalogReturn } from "./catalog-return";
import { showContentLocaleNote } from "./content-locale";
import { useProduct } from "./hooks";
import { AvailabilityBadge, CaStatusBadge, EpiBadge } from "./product-badges";

interface ProductDetailViewProps {
  productId: string;
}

export function ProductDetailView({ productId }: ProductDetailViewProps) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const query = useProduct(productId);
  const [quantity, setQuantity] = React.useState<number | null>(null);

  React.useEffect(() => {
    setQuantity(null);
  }, [productId]);

  function handleBackToCatalog() {
    router.push(readCatalogReturn() ?? "/catalog");
  }

  if (query.isLoading) {
    return (
      <div className="grid gap-8 lg:grid-cols-2">
        <Skeleton className="aspect-square w-full rounded-3xl" />
        <div className="space-y-4">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-10 w-3/4" />
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
        </div>
      </div>
    );
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("catalog.loadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(query.error))}</AlertDescription>
      </Alert>
    );
  }

  const product = query.data;
  if (!product) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("catalog.noResults")}</AlertDescription>
      </Alert>
    );
  }

  const sellable = isPurchasable(product);
  const minQuantity = Math.max(1, product.min_order_qty);
  const stockQuantity = product.stock_quantity ?? 0;
  const maxQuantity = Math.max(minQuantity, stockQuantity);
  const selectedQuantity = Math.min(maxQuantity, Math.max(minQuantity, quantity ?? minQuantity));
  const hasStock = stockQuantity > 0;

  function updateQuantity(next: number) {
    if (Number.isNaN(next)) {
      return;
    }
    setQuantity(Math.min(maxQuantity, Math.max(minQuantity, Math.floor(next))));
  }

  return (
    <div className="space-y-8">
      <nav className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <button
          type="button"
          onClick={handleBackToCatalog}
          className="inline-flex items-center gap-1.5 font-medium text-foreground transition-colors hover:text-forge-700 dark:hover:text-forge-300"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4 rtl:-scale-x-100" />
          {t("catalog.backToCatalog")}
        </button>
        <span aria-hidden="true">/</span>
        <span className="truncate">{displayCategoryName(product.category.name)}</span>
        <span aria-hidden="true">/</span>
        <span className="truncate text-foreground/70">{product.name}</span>
      </nav>

      <div className="grid gap-8 lg:grid-cols-[1.02fr_0.98fr] lg:gap-12">
        <div className="space-y-4">
          <div className="relative overflow-hidden rounded-3xl border border-border bg-card">
            <div className="absolute start-4 top-4 z-10 flex flex-wrap gap-1.5">
              <EpiBadge isEpi={product.is_epi} />
              <CaStatusBadge status={product.ca_status} />
              <AvailabilityBadge isSellable={sellable} />
            </div>
            <div className="flex aspect-square items-center justify-center">
              <ProductImage
                src={product.image_url}
                alt={product.image_alt}
                className="h-full w-full"
              />
            </div>
            <div className="pointer-events-none absolute end-5 top-5 h-24 w-24 rounded-full bg-primary/5" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: BadgeCheck, label: t("home.trustCnpj") },
              { icon: PackageCheck, label: t("home.trustNational") },
              { icon: ShieldCheck, label: t("home.trustSecure") },
            ].map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card px-2 py-4 text-center"
              >
                <Icon aria-hidden="true" className="h-4 w-4 text-primary" />
                <span className="text-[11px] font-medium leading-tight text-muted-foreground">
                  {label}
                </span>
              </div>
            ))}
          </div>

          <div className="hidden rounded-2xl border border-border bg-card p-6 lg:block">
            <ul className="space-y-5">
              {[
                {
                  icon: BadgePercent,
                  title: t("cart.benefit1Title"),
                  description: t("cart.benefit1Description"),
                },
                {
                  icon: CreditCard,
                  title: t("cart.benefit2Title"),
                  description: t("cart.benefit2Description"),
                },
                {
                  icon: Truck,
                  title: t("cart.benefit3Title"),
                  description: t("cart.benefit3Description"),
                },
              ].map(({ icon: Icon, title, description }) => (
                <li key={title} className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                    <Icon aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">{title}</span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                      {description}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="space-y-6">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-forge-700 dark:text-forge-300">
              {displayCategoryName(product.category.name)}
            </p>
            <h1 className="mt-2 text-3xl font-black leading-tight tracking-tight sm:text-4xl">
              {product.name}
            </h1>
            <p className="mt-3 font-mono text-xs text-muted-foreground">
              {t("catalog.sku")}: {product.sku}
              {product.brand ? ` · ${product.brand.name}` : ""}
            </p>
            {showContentLocaleNote(locale, product.content_locale) ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {t("catalog.contentDisplayedIn", {
                  locale:
                    product.content_locale && isLocale(product.content_locale)
                      ? localeLabels[product.content_locale]
                      : product.content_locale,
                })}
              </p>
            ) : null}
          </div>

          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
            <CatalogPrice
              amount={product.base_unit_price}
              currency={product.currency}
              priceOnRequest={product.price_on_request}
              className="text-3xl font-black tracking-tight"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              {t("catalog.minOrderQty")}:{" "}
              <span className="font-semibold text-foreground">{minQuantity}</span>
              {product.unit_of_measure ? ` · ${product.unit_of_measure}` : ""}
            </p>
            <p
              className={
                hasStock
                  ? "mt-2 flex items-center gap-1.5 text-sm font-semibold text-success"
                  : "mt-2 flex items-center gap-1.5 text-sm font-semibold text-destructive"
              }
            >
              <PackageCheck aria-hidden="true" className="h-4 w-4" />
              {hasStock
                ? t("catalog.stockAvailable", { count: stockQuantity })
                : t("catalog.outOfStock")}
            </p>

            <div className="mt-5 space-y-2">
              <Label
                htmlFor="product-quantity"
                className="text-xs font-medium text-muted-foreground"
              >
                {t("cart.quantity")}
              </Label>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-11 w-11 shrink-0 rounded-xl"
                  aria-label={t("cart.decreaseQuantity")}
                  disabled={!sellable || selectedQuantity <= minQuantity}
                  onClick={() => updateQuantity(selectedQuantity - 1)}
                >
                  <Minus aria-hidden="true" className="h-4 w-4" />
                </Button>
                <Input
                  id="product-quantity"
                  type="number"
                  inputMode="numeric"
                  min={minQuantity}
                  max={maxQuantity}
                  step={1}
                  value={selectedQuantity}
                  disabled={!sellable}
                  className="h-11 w-24 rounded-xl text-center text-base font-semibold tabular-nums"
                  onFocus={(event) => event.currentTarget.select()}
                  onChange={(event) => updateQuantity(Number.parseInt(event.target.value, 10))}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-11 w-11 shrink-0 rounded-xl"
                  aria-label={t("cart.increaseQuantity")}
                  disabled={!sellable || selectedQuantity >= maxQuantity}
                  onClick={() => updateQuantity(selectedQuantity + 1)}
                >
                  <Plus aria-hidden="true" className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="mt-4 grid gap-2">
              <BuyNowButton
                productId={product.id}
                minQuantity={minQuantity}
                quantity={selectedQuantity}
                disabled={!sellable}
                size="lg"
                className="h-12 w-full rounded-xl text-sm font-semibold"
              />
              <AddToCartButton
                productId={product.id}
                minQuantity={minQuantity}
                quantity={selectedQuantity}
                disabled={!sellable}
                size="lg"
                className="h-12 w-full rounded-xl text-sm font-semibold"
              />
            </div>

            {!sellable ? (
              <p className="mt-3 text-center text-xs font-medium text-destructive">
                {t("catalog.notSellable")}
              </p>
            ) : null}
          </div>

          {product.description ? (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {t("catalog.description")}
              </h2>
              <p className="text-sm leading-relaxed text-foreground/80">{product.description}</p>
            </section>
          ) : null}

          <section className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {t("catalog.details")}
            </h2>
            <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted-foreground">{t("catalog.category")}</dt>
                <dd className="mt-0.5 text-sm font-medium">
                  {displayCategoryName(product.category.name)}
                </dd>
              </div>
              {product.brand ? (
                <div>
                  <dt className="text-xs text-muted-foreground">{t("catalog.brand")}</dt>
                  <dd className="mt-0.5 text-sm font-medium">{product.brand.name}</dd>
                </div>
              ) : null}
              {product.unit_of_measure ? (
                <div>
                  <dt className="text-xs text-muted-foreground">{t("catalog.unit")}</dt>
                  <dd className="mt-0.5 text-sm font-medium">{product.unit_of_measure}</dd>
                </div>
              ) : null}
              {product.weight_kg != null ? (
                <div>
                  <dt className="text-xs text-muted-foreground">{t("catalog.weight")}</dt>
                  <dd className="mt-0.5 text-sm font-medium">
                    {t("catalog.weightKg", {
                      weight: formatNumber(Number(product.weight_kg), locale),
                    })}
                  </dd>
                </div>
              ) : null}
              {product.ca_number ? (
                <div>
                  <dt className="text-xs text-muted-foreground">{t("catalog.caNumber")}</dt>
                  <dd className="mt-0.5 text-sm font-medium">{product.ca_number}</dd>
                </div>
              ) : null}
              {product.ncm ? (
                <div>
                  <dt className="text-xs text-muted-foreground">{t("catalog.ncm")}</dt>
                  <dd className="mt-0.5 font-mono text-sm font-medium">{product.ncm}</dd>
                </div>
              ) : null}
            </dl>
          </section>

          {product.attributes.length > 0 ? (
            <section className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {t("catalog.attributes")}
              </h2>
              <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
                {product.attributes.map((attribute) => (
                  <div key={attribute.key}>
                    <dt className="text-xs text-muted-foreground">{attribute.label}</dt>
                    <dd className="mt-0.5 text-sm font-medium">
                      {attribute.value}
                      {attribute.unit ? (
                        <span className="ms-1 text-muted-foreground">({attribute.unit})</span>
                      ) : null}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
