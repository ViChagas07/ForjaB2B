"use client";

import * as React from "react";
import { CreditCard as CreditCardIcon, LockKeyhole, ShieldCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import type { Cart } from "@/core/domain/cart";
import type { CreditAccount } from "@/core/domain/credit";
import { newIdempotencyKey } from "@/core/domain/idempotency";
import type { PaymentMethod } from "@/core/domain/ordering";
import { PAYMENT_METHODS } from "@/core/domain/ordering";
import { Link } from "@/i18n/navigation";
import { ProductImage } from "@/shared/components/product-image";
import { errorMessageKey } from "@/shared/lib/api-error";
import { DEFAULT_CURRENCY, formatMoney } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader } from "@/shared/ui/card";

interface CheckoutViewProps {
  cart: Cart;
  cartError: unknown;
  credit: CreditAccount | undefined;
  stripeEnabled: boolean;
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
  stripeEnabled,
  isPlacingOrder,
  orderError,
  onPlaceOrder,
}: CheckoutViewProps) {
  const t = useTranslations();
  const locale = useLocale();
  const status = useAuthStore((s) => s.status);
  const session = useAuthStore((s) => s.session);
  const isConsumer = (session?.user.account_type ?? "COMPANY") === "PERSON";

  const [paymentMethod, setPaymentMethod] = React.useState<PaymentMethod>("PIX");
  const [notes, setNotes] = React.useState("");
  // Uma chave por tentativa de envio (montagem do checkout). Retentativas do
  // mesmo formulario reutilizam a chave; o backend responde o pedido original.
  const [idempotencyKey] = React.useState(newIdempotencyKey);

  if (status !== "authenticated") {
    return (
      <Card className="mx-auto w-full max-w-md rounded-2xl">
        <CardHeader>
          <h1 className="text-2xl font-black tracking-tight">{t("ordering.reviewTitle")}</h1>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="warning">
            <AlertDescription>{t("dashboard.loginRequired")}</AlertDescription>
          </Alert>
          <Button asChild className="w-full rounded-xl">
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

  const availableMethods = PAYMENT_METHODS.filter((method) => {
    if (method === "CARD") {
      return stripeEnabled;
    }
    // Boleto é crédito faturado B2B: não existe para consumidor (PF) e exige
    // conta de crédito ativa para empresa.
    if (method === "BOLETO") {
      return !isConsumer && Boolean(credit);
    }
    return true;
  });

  function methodLabel(method: PaymentMethod): string {
    if (method === "PIX") return t("ordering.pix");
    if (method === "CARD") return t("ordering.card");
    return t("ordering.boleto");
  }

  function methodDescription(method: PaymentMethod): string {
    if (method === "PIX") return t("ordering.pixDescription");
    if (method === "CARD") return t("ordering.cardDescription");
    return t("ordering.boletoDescription");
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onPlaceOrder(paymentMethod, notes.trim() ? notes.trim() : "", idempotencyKey);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-forge-700 dark:text-forge-300">
          {t("cart.checkout")}
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          {t("ordering.reviewTitle")}
        </h1>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
          <div className="space-y-6">
            <Card className="rounded-2xl">
              <CardHeader>
                <h2 className="text-base font-bold">{t("ordering.items")}</h2>
              </CardHeader>
              <CardContent className="divide-y divide-border p-0">
                {items.map((item) => (
                  <div key={item.product_id} className="flex items-center gap-4 px-6 py-4">
                    <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-border bg-secondary/60">
                      <ProductImage
                        src={item.image_url}
                        alt={item.image_alt}
                        className="h-full w-full object-contain p-1.5"
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-sm font-semibold">{item.name}</p>
                      <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                        {t("catalog.sku")}: {item.sku} · {item.quantity} ×{" "}
                        {formatMoney(item.unit_price, DEFAULT_CURRENCY, locale)}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-bold">
                      {formatMoney(item.line_total, DEFAULT_CURRENCY, locale)}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-2xl">
              <CardHeader>
                <h2 className="text-base font-bold">{t("ordering.paymentMethod")}</h2>
              </CardHeader>
              <CardContent className="space-y-3">
                {availableMethods.map((method) => {
                  const selected = paymentMethod === method;
                  const label = methodLabel(method);
                  const description = methodDescription(method);
                  return (
                    <button
                      key={method}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => setPaymentMethod(method)}
                      className={`flex w-full items-start gap-3 rounded-xl border p-4 text-start transition-colors ${
                        selected
                          ? "border-primary bg-accent/40 ring-1 ring-primary/30"
                          : "border-border bg-card hover:border-primary/40"
                      }`}
                    >
                      <span
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                          selected ? "border-primary" : "border-input"
                        }`}
                      >
                        {selected ? <span className="h-2.5 w-2.5 rounded-full bg-primary" /> : null}
                      </span>
                      <span className="space-y-0.5">
                        <span className="block text-sm font-semibold">{label}</span>
                        <span className="block text-xs leading-relaxed text-muted-foreground">
                          {description}
                        </span>
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

            <Card className="rounded-2xl">
              <CardHeader>
                <h2 className="text-base font-bold">{t("ordering.notes")}</h2>
              </CardHeader>
              <CardContent>
                <textarea
                  id="order-notes"
                  className="flex min-h-24 w-full rounded-xl border border-input bg-card px-3 py-2 text-sm shadow-none transition-colors placeholder:text-muted-foreground focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder={t("ordering.notesPlaceholder")}
                />
              </CardContent>
            </Card>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24">
            <Card className="rounded-2xl">
              <CardContent className="space-y-4 p-5">
                <h2 className="text-base font-bold">{t("ordering.summaryTitle")}</h2>

                <dl className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <dt className="text-muted-foreground">{t("ordering.subtotal")}</dt>
                    <dd className="font-semibold">
                      {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
                    </dd>
                  </div>
                  {credit != null ? (
                    <div className="flex items-center justify-between">
                      <dt className="text-muted-foreground">{t("credit.available")}</dt>
                      <dd className="font-semibold" data-testid="credit-available">
                        {formatMoney(credit.available, DEFAULT_CURRENCY, locale)}
                      </dd>
                    </div>
                  ) : null}
                  <div className="flex items-center justify-between border-t border-border pt-3">
                    <dt className="text-base font-bold">{t("ordering.total")}</dt>
                    <dd className="text-xl font-black tracking-tight">
                      {formatMoney(cart.subtotal, DEFAULT_CURRENCY, locale)}
                    </dd>
                  </div>
                </dl>

                {orderError ? (
                  <Alert variant="destructive">
                    <AlertDescription>{t(errorMessageKey(orderError))}</AlertDescription>
                  </Alert>
                ) : null}

                <Button
                  type="submit"
                  size="lg"
                  className="h-12 w-full rounded-xl text-sm font-semibold"
                  disabled={isPlacingOrder}
                >
                  <LockKeyhole aria-hidden="true" />
                  {isPlacingOrder ? t("ordering.placingOrder") : t("ordering.placeOrder")}
                </Button>

                <Button asChild variant="ghost" size="sm" className="w-full rounded-lg">
                  <Link href="/cart">{t("ordering.backToCart")}</Link>
                </Button>

                <p className="flex items-start gap-2 text-[11px] leading-relaxed text-muted-foreground">
                  <ShieldCheck
                    aria-hidden="true"
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary"
                  />
                  {t("cart.secureNote")}
                </p>
              </CardContent>
            </Card>

            {credit != null ? (
              <div className="rounded-2xl border border-border bg-card p-5">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <CreditCardIcon aria-hidden="true" className="h-4 w-4 text-primary" />
                  {t("credit.accountTitle")}
                </div>
                <dl className="mt-3 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">{t("credit.limit")}</dt>
                    <dd className="font-semibold">
                      {formatMoney(credit.credit_limit, DEFAULT_CURRENCY, locale)}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">{t("credit.used")}</dt>
                    <dd className="font-semibold">
                      {formatMoney(credit.used, DEFAULT_CURRENCY, locale)}
                    </dd>
                  </div>
                </dl>
              </div>
            ) : null}
          </aside>
        </div>
      </form>
    </div>
  );
}
