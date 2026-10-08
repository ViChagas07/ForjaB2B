"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { Cart } from "@/core/domain/cart";
import type { CreditAccount } from "@/core/domain/credit";
import type { PaymentMethod } from "@/core/domain/ordering";
import { PAYMENT_METHODS } from "@/core/domain/ordering";
import { formatMoney, DEFAULT_CURRENCY } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Separator } from "@/shared/ui/separator";
import { errorMessageKey } from "@/shared/lib/api-error";

interface CheckoutViewProps {
  cart: Cart;
  cartError: unknown;
  credit: CreditAccount | undefined;
  isPlacingOrder: boolean;
  orderError: unknown;
  onPlaceOrder: (paymentMethod: PaymentMethod, notes: string, idempotencyKey: string) => void;
}

/**
 * Revisão do pedido (estado "burro"): recebe dados/callbacks da composição no
 * app. Não mantém autoridade financeira — o total exibido é um espelho do
 * carrinho; o backend recalcula e responde o valor definitivo.
 */
export function CheckoutView({
  cart,
  cartError,
  credit,
  isPlacingOrder,
  orderError,
  onPlaceOrder,
}: CheckoutViewProps) {
  const t = useTranslations();
  const locale = useLocale();
  const status = useAuthStore((s) => s.status);

  const [paymentMethod, setPaymentMethod] = React.useState<PaymentMethod>("PIX");
  const [notes, setNotes] = React.useState("");
  const [idempotencyKey] = React.useState(() => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `order-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  });

  if (status !== "authenticated") {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("ordering.reviewTitle")}</CardTitle>
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

  if (cartError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("cart.loadError")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(cartError))}</AlertDescription>
      </Alert>
    );
  }

  const items = cart.items ?? [];
  if (items.length === 0) {
    return (
      <Alert variant="info">
        <AlertDescription>{t("cart.empty")}</AlertDescription>
      </Alert>
    );
  }

  const isBoleto = paymentMethod === "BOLETO";
  const subtotal = Number(cart.subtotal);
  const available = credit ? Number(credit.available) : null;
  const creditInsufficient = isBoleto && available != null && available < subtotal;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onPlaceOrder(paymentMethod, notes.trim() ? notes.trim() : "", idempotencyKey);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("ordering.reviewTitle")}</h1>

      <Card>
        <CardHeader>
          <CardTitle>{t("ordering.items")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {items.map((item) => (
            <div key={item.product_id} className="flex items-center justify-between text-sm">
              <div>
                <span className="font-medium">{item.name}</span>
                <span className="text-muted-foreground"> × {item.quantity}</span>
              </div>
              <span className="font-medium">
                {formatMoney(item.line_total, DEFAULT_CURRENCY, locale)}
              </span>
            </div>
          ))}
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">{t("ordering.subtotal")}</span>
            <span className="font-semibold">
              {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
            </span>
          </div>
        </CardContent>
      </Card>

      {credit != null ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("credit.accountTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-3">
            <div>
              <p className="text-sm text-muted-foreground">{t("credit.available")}</p>
              <p className="font-semibold" data-testid="credit-available">
                {formatMoney(credit.available, DEFAULT_CURRENCY, locale)}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t("credit.limit")}</p>
              <p className="font-semibold">
                {formatMoney(credit.credit_limit, DEFAULT_CURRENCY, locale)}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t("credit.used")}</p>
              <p className="font-semibold">{formatMoney(credit.used, DEFAULT_CURRENCY, locale)}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("ordering.paymentMethod")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {PAYMENT_METHODS.map((method) => {
            const selected = paymentMethod === method;
            const label = method === "PIX" ? "PIX" : "Boleto";
            const description =
              method === "PIX" ? t("ordering.pixDescription") : t("ordering.boletoDescription");
            return (
              <button
                key={method}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setPaymentMethod(method)}
                className={`flex w-full items-start gap-3 rounded-md border p-3 text-left ${
                  selected ? "border-primary ring-1 ring-ring" : "border-input"
                }`}
              >
                <span
                  className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                    selected ? "border-primary" : "border-input"
                  }`}
                >
                  {selected ? <span className="h-2 w-2 rounded-full bg-primary" /> : null}
                </span>
                <span>
                  <span className="block font-medium">{label}</span>
                  <span className="text-sm text-muted-foreground">{description}</span>
                </span>
              </button>
            );
          })}

          {creditInsufficient ? (
            <Alert variant="destructive">
              <AlertTitle>{t("ordering.creditInsufficient")}</AlertTitle>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="order-notes" className="text-sm font-medium">
            {t("ordering.notes")}
          </label>
          <textarea
            id="order-notes"
            className="flex min-h-20 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder={t("ordering.notesPlaceholder")}
          />
        </div>

        {orderError ? (
          <Alert variant="destructive">
            <AlertDescription>{t(errorMessageKey(orderError))}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">{t("ordering.total")}</p>
            <p className="text-2xl font-bold">
              {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
            </p>
          </div>
          <Button type="submit" size="lg" disabled={isPlacingOrder}>
            {isPlacingOrder ? t("ordering.placingOrder") : t("ordering.placeOrder")}
          </Button>
        </div>
      </form>
    </div>
  );
}
