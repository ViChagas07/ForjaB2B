"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { Minus, Plus, Trash2 } from "lucide-react";

import { Link, useRouter } from "@/i18n/navigation";
import type { CartItem } from "@/core/domain/cart";
import { formatMoney, DEFAULT_CURRENCY } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { errorMessageKey } from "@/shared/lib/api-error";

import { useCart, useClearCart, useRemoveCartItem, useUpdateCartItem } from "./hooks";

export function CartView() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const status = useAuthStore((s) => s.status);

  const cartQuery = useCart();
  const updateMutation = useUpdateCartItem();
  const removeMutation = useRemoveCartItem();
  const clearMutation = useClearCart();

  const [formError, setFormError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const error = updateMutation.error ?? removeMutation.error ?? clearMutation.error;
    setFormError(error ? t(errorMessageKey(error)) : null);
  }, [updateMutation.error, removeMutation.error, clearMutation.error, t]);

  if (status !== "authenticated") {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("cart.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="warning">
            <AlertDescription>{t("dashboard.loginRequired")}</AlertDescription>
          </Alert>
          <Button asChild className="w-full">
            <Link href="/login">{t("dashboard.loginLink")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (cartQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-64 w-full" />
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
  if (!cart) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("cart.empty")}</AlertDescription>
      </Alert>
    );
  }
  const items = cart.items;

  if (items.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t("cart.title")}</h1>
        <Alert variant="info">
          <AlertDescription>{t("cart.empty")}</AlertDescription>
        </Alert>
        <Button asChild variant="outline">
          <Link href="/catalog">{t("cart.browseProducts")}</Link>
        </Button>
      </div>
    );
  }

  function setQuantity(item: CartItem, delta: number) {
    const next = item.quantity + delta;
    if (next < 1) {
      return;
    }
    updateMutation.mutate({ productId: item.product_id, input: { quantity: next } });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("cart.title")}</h1>
        <Button
          variant="outline"
          size="sm"
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

      <Card>
        <CardContent className="divide-y">
          {items.map((item) => (
            <div key={item.product_id} className="flex flex-wrap items-center gap-4 py-4">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-muted-foreground">
                  {t("catalog.sku")}: <span className="font-mono">{item.sku}</span>
                  {item.tier_min_quantity != null
                    ? ` · ${t("cart.tierApplied")} (≥ ${item.tier_min_quantity})`
                    : ""}
                </p>
                <p className="text-sm">
                  {formatMoney(item.unit_price, DEFAULT_CURRENCY, locale)}
                  <span className="text-muted-foreground"> × {item.quantity}</span>
                </p>
              </div>

              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="−"
                  disabled={updateMutation.isPending}
                  onClick={() => setQuantity(item, -1)}
                >
                  <Minus aria-hidden="true" />
                </Button>
                <span className="w-10 text-center font-medium tabular-nums">{item.quantity}</span>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="+"
                  disabled={updateMutation.isPending}
                  onClick={() => setQuantity(item, 1)}
                >
                  <Plus aria-hidden="true" />
                </Button>
              </div>

              <div className="w-28 text-right font-semibold">
                {formatMoney(item.line_total, DEFAULT_CURRENCY, locale)}
              </div>

              <Button
                variant="ghost"
                size="icon"
                aria-label={t("cart.remove")}
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(item.product_id)}
              >
                <Trash2 aria-hidden="true" />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 py-6">
          <div>
            <p className="text-sm text-muted-foreground">{t("cart.subtotal")}</p>
            <p className="text-2xl font-bold">
              {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
            </p>
          </div>
          <Button size="lg" onClick={() => router.push("/checkout")}>
            {t("cart.checkout")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
