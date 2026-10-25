"use client";

import * as React from "react";
import {
  BadgePercent,
  Check,
  ChevronRight,
  CreditCard,
  LockKeyhole,
  Minus,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Trash2,
  Truck,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import type { CartItem } from "@/core/domain/cart";
import { useCreditAccount } from "@/features/credit";
import { Link, useRouter } from "@/i18n/navigation";
import { errorMessageKey } from "@/shared/lib/api-error";
import { DEFAULT_CURRENCY, formatMoney } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";

import { ProductImage } from "@/shared/components/product-image";
import { cn } from "@/shared/lib/utils";

import { useCart, useClearCart, useRemoveCartItem, useUpdateCartItem } from "./hooks";

const STEPS = ["cart.title", "ordering.shippingTotal", "ordering.paymentMethod"] as const;

export function CartView() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const status = useAuthStore((s) => s.status);

  const cartQuery = useCart();
  const creditQuery = useCreditAccount();
  const updateMutation = useUpdateCartItem();
  const removeMutation = useRemoveCartItem();
  const clearMutation = useClearCart();

  const [formError, setFormError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const error = updateMutation.error ?? removeMutation.error ?? clearMutation.error;
    setFormError(error ? t(errorMessageKey(error)) : null);
  }, [updateMutation.error, removeMutation.error, clearMutation.error, t]);

  function setQuantity(item: CartItem, delta: number) {
    const next = item.quantity + delta;
    if (next < 1) {
      return;
    }
    updateMutation.mutate({ productId: item.product_id, input: { quantity: next } });
  }

  const steps = (
    <ol className="flex flex-wrap items-center gap-2 text-xs font-medium text-muted-foreground">
      {STEPS.map((key, index) => {
        const active = index === 0;
        return (
          <li key={key} className="flex items-center gap-2">
            <span
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-bold",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground",
              )}
            >
              {active ? <Check aria-hidden="true" className="h-3 w-3" /> : index + 1}
            </span>
            <span className={active ? "text-foreground" : undefined}>{t(key)}</span>
            {index < STEPS.length - 1 ? (
              <span
                aria-hidden="true"
                className="mx-1 h-px w-8 border-t border-dashed border-border"
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );

  if (status !== "authenticated") {
    return (
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="space-y-3">
          <nav className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link
              href="/"
              className="transition-colors hover:text-forge-700 dark:hover:text-forge-300"
            >
              {t("cart.breadcrumbHome")}
            </Link>
            <ChevronRight aria-hidden="true" className="h-3 w-3 rtl:-scale-x-100" />
            <span className="text-foreground">{t("cart.pageTitle")}</span>
          </nav>
          {steps}
        </div>

        <div className="mx-auto max-w-lg rounded-3xl border border-border bg-card p-8 text-center shadow-sm sm:p-12">
          <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <LockKeyhole aria-hidden="true" className="h-7 w-7" />
          </span>
          <h1 className="mt-6 text-2xl font-black tracking-tight">{t("cart.pageTitle")}</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {t("authGate.description")}
          </p>
          <div className="mt-7 grid gap-2">
            <Button asChild size="lg" className="rounded-xl">
              <Link href="/login">{t("nav.login")}</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="rounded-xl">
              <Link href="/onboarding">{t("nav.register")}</Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (cartQuery.isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-8">
        <Skeleton className="h-6 w-56" />
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <Skeleton className="h-80 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (cartQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("cart.loadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(cartQuery.error))}</AlertDescription>
      </Alert>
    );
  }

  const cart = cartQuery.data;
  const items = cart?.items ?? [];
  const availableCredit = creditQuery.data?.available;
  const itemCountLabel =
    items.length === 1 ? t("cart.itemCountOne") : t("cart.itemsCount", { count: items.length });

  if (!cart || items.length === 0) {
    return (
      <div className="mx-auto max-w-5xl space-y-8">
        <div className="space-y-3">
          <nav className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link
              href="/"
              className="transition-colors hover:text-forge-700 dark:hover:text-forge-300"
            >
              {t("cart.breadcrumbHome")}
            </Link>
            <ChevronRight aria-hidden="true" className="h-3 w-3 rtl:-scale-x-100" />
            <span className="text-foreground">{t("cart.pageTitle")}</span>
          </nav>
          {steps}
        </div>

        <div className="mx-auto max-w-lg rounded-3xl border border-border bg-card p-8 text-center shadow-sm sm:p-12">
          <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <ShoppingBag aria-hidden="true" className="h-7 w-7" />
          </span>
          <h1 className="mt-6 text-2xl font-black tracking-tight">{t("cart.empty")}</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {t("cart.emptyDescription")}
          </p>
          <Button asChild size="lg" className="mt-7 rounded-xl">
            <Link href="/catalog">{t("cart.browseProducts")}</Link>
          </Button>
        </div>
      </div>
    );
  }

  const benefits = [
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
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="space-y-3">
        <nav className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link
            href="/"
            className="transition-colors hover:text-forge-700 dark:hover:text-forge-300"
          >
            {t("cart.breadcrumbHome")}
          </Link>
          <ChevronRight aria-hidden="true" className="h-3 w-3 rtl:-scale-x-100" />
          <span className="text-foreground">{t("cart.pageTitle")}</span>
        </nav>
        {steps}
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black tracking-tight sm:text-4xl">{t("cart.pageTitle")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{itemCountLabel}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="rounded-lg text-muted-foreground hover:text-destructive"
          disabled={clearMutation.isPending}
          onClick={() => clearMutation.mutate()}
        >
          <Trash2 aria-hidden="true" />
          {t("cart.clear")}
        </Button>
      </div>

      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">{t("ordering.items")}</h2>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[11px] font-semibold text-secondary-foreground">
              {itemCountLabel}
            </span>
          </div>

          <ul className="divide-y divide-border">
            {items.map((item) => (
              <li
                key={item.product_id}
                className="flex flex-col gap-4 p-4 sm:p-5 lg:flex-row lg:items-center"
              >
                <Link
                  href={`/catalog/${item.product_id}`}
                  className="relative h-24 w-24 shrink-0 overflow-hidden rounded-xl border border-border bg-secondary/60"
                >
                  <ProductImage
                    src={item.image_url}
                    alt={item.image_alt}
                    className="h-full w-full object-contain p-2"
                  />
                </Link>

                <div className="min-w-0 flex-1">
                  <Link
                    href={`/catalog/${item.product_id}`}
                    className="line-clamp-2 text-sm font-semibold transition-colors hover:text-forge-700 dark:hover:text-forge-300"
                  >
                    {item.name}
                  </Link>
                  <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                    {t("catalog.sku")}: {item.sku}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {t("ordering.unitPrice")}:{" "}
                      <span className="font-semibold text-foreground">
                        {formatMoney(item.unit_price, DEFAULT_CURRENCY, locale)}
                      </span>
                    </span>
                    {item.tier_min_quantity != null ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold text-accent-foreground">
                        {t("cart.tierApplied")}
                        <span className="tabular-nums">≥ {item.tier_min_quantity}</span>
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="flex items-center gap-1 self-start lg:self-center">
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label="−"
                    className="h-8 w-8 rounded-lg"
                    disabled={updateMutation.isPending}
                    onClick={() => setQuantity(item, -1)}
                  >
                    <Minus aria-hidden="true" />
                  </Button>
                  <span className="w-9 text-center text-sm font-semibold tabular-nums">
                    {item.quantity}
                  </span>
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label="+"
                    className="h-8 w-8 rounded-lg"
                    disabled={updateMutation.isPending}
                    onClick={() => setQuantity(item, 1)}
                  >
                    <Plus aria-hidden="true" />
                  </Button>
                </div>

                <div className="flex items-center justify-between gap-4 lg:w-32 lg:justify-end">
                  <div className="lg:text-end">
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground lg:hidden">
                      {t("cart.itemTotal")}
                    </p>
                    <p className="text-sm font-bold">
                      {formatMoney(item.line_total, DEFAULT_CURRENCY, locale)}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("cart.remove")}
                    className="h-8 w-8 rounded-lg text-muted-foreground hover:text-destructive"
                    disabled={removeMutation.isPending}
                    onClick={() => removeMutation.mutate(item.product_id)}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24">
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-bold tracking-tight">{t("ordering.summaryTitle")}</h2>

            <dl className="mt-5 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-muted-foreground">{t("cart.subtotal")}</dt>
                <dd className="font-semibold">
                  {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-muted-foreground">{t("ordering.shippingTotal")}</dt>
                <dd className="text-xs font-medium text-muted-foreground">
                  {t("cart.shippingCalculated")}
                </dd>
              </div>
              <div className="flex items-center justify-between border-t border-border pt-3">
                <dt className="text-base font-bold">{t("ordering.total")}</dt>
                <dd className="text-xl font-black tracking-tight">
                  {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
                </dd>
              </div>
            </dl>

            {availableCredit ? (
              <div className="mt-5 flex items-center justify-between rounded-xl bg-accent/70 px-3.5 py-3">
                <span className="text-xs font-medium text-accent-foreground">
                  {t("credit.available")}
                </span>
                <span className="text-sm font-bold text-accent-foreground">
                  {formatMoney(availableCredit, DEFAULT_CURRENCY, locale)}
                </span>
              </div>
            ) : null}

            <Button
              size="lg"
              className="mt-5 h-12 w-full rounded-xl text-sm font-semibold"
              onClick={() => router.push("/checkout")}
            >
              {t("cart.checkout")}
              <ChevronRight aria-hidden="true" className="rtl:-scale-x-100" />
            </Button>

            <p className="mt-4 flex items-start gap-2 text-[11px] leading-relaxed text-muted-foreground">
              <ShieldCheck
                aria-hidden="true"
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary"
              />
              {t("cart.secureNote")}
            </p>
          </div>

          <div className="space-y-3">
            {benefits.map(({ icon: Icon, title, description }) => (
              <div
                key={title}
                className="flex items-start gap-3 rounded-xl border border-border bg-card p-4"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <Icon aria-hidden="true" className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-xs font-semibold">{title}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
                    {description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
