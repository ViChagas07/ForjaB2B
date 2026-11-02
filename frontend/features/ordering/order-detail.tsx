"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";

import { Link } from "@/i18n/navigation";
import type { OrderStatus } from "@/core/domain/ordering";
import { formatBrl, formatDate } from "@/shared/lib/money";
import { CnpjPrice, CnpjVolumeNotice } from "@/shared/components/cnpj-price";
import { PriceDisplay } from "@/shared/components/price-display";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { errorMessageKey } from "@/shared/lib/api-error";

import { useCancelOrder, useOrder } from "./hooks";

const CANCELLABLE: readonly OrderStatus[] = ["RECEIVED", "CREDIT_REVIEW"];

function statusLabelKey(status: string): string {
  switch (status) {
    case "RECEIVED":
      return "ordering.statusReceived";
    case "CREDIT_REVIEW":
      return "ordering.statusCreditReview";
    case "PAID":
      return "ordering.statusPaid";
    case "INVOICED":
      return "ordering.statusInvoiced";
    case "IN_TRANSIT":
      return "ordering.statusInTransit";
    case "DELIVERED":
      return "ordering.statusDelivered";
    case "CANCELLED":
      return "ordering.statusCancelled";
    case "CREDIT_REJECTED":
      return "ordering.statusCreditRejected";
    default:
      return "";
  }
}

interface OrderDetailViewProps {
  orderId: string;
}

export function OrderDetailView({ orderId }: OrderDetailViewProps) {
  const t = useTranslations();
  const locale = useLocale();
  const orderQuery = useOrder(orderId);
  const cancelMutation = useCancelOrder();

  if (orderQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (orderQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("ordering.orderNotFound")}</AlertTitle>
        <AlertDescription>{t(errorMessageKey(orderQuery.error))}</AlertDescription>
      </Alert>
    );
  }

  const order = orderQuery.data;
  if (!order) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("ordering.orderNotFound")}</AlertDescription>
      </Alert>
    );
  }

  const statusKey = statusLabelKey(order.status);
  const cancellable = (CANCELLABLE as readonly string[]).includes(order.status);
  const cnpjDiscountTotal = order.cnpj_discount_total ?? "0.00";
  const hasCnpjDiscount = Number(cnpjDiscountTotal) > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/dashboard">
            <ArrowLeft aria-hidden="true" className="rtl:-scale-x-100" />
            {t("ordering.back")}
          </Link>
        </Button>
        <Badge variant={order.status === "CANCELLED" ? "destructive" : "default"}>
          {statusKey ? t(statusKey) : order.status}
        </Badge>
      </div>

      <div className="flex items-start justify-between gap-2">
        <h1 className="text-2xl font-black tracking-tight sm:text-3xl">
          {t("ordering.orderNumber")} <span className="font-mono">{order.id}</span>
        </h1>
      </div>

      {cancelMutation.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{t(errorMessageKey(cancelMutation.error))}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("ordering.items")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {order.items.map((item) => (
            <div key={item.sku} className="flex items-start justify-between gap-3 text-sm">
              <div className="min-w-0">
                <span className="font-medium">{item.product_name}</span>
                <span className="text-muted-foreground">
                  {" "}
                  ({item.sku}) × {item.quantity}
                </span>
                {Number(item.cnpj_discount_percent ?? 0) > 0 ? (
                  <div className="mt-1.5">
                    <CnpjPrice
                      listAmount={item.list_unit_price}
                      finalAmount={item.unit_price}
                      percent={item.cnpj_discount_percent}
                      primary="brl"
                      showBrl
                      priceClassName="text-sm font-bold"
                    />
                    <CnpjVolumeNotice band={item.cnpj_discount_band} />
                  </div>
                ) : null}
              </div>
              <div className="shrink-0 text-end">
                <span className="font-medium">{formatBrl(item.line_total, locale)}</span>
                {Number(item.cnpj_discount_amount ?? 0) > 0 ? (
                  <span className="mt-0.5 block text-[11px] font-semibold text-success">
                    <span className="sr-only">{t("ordering.cnpjDiscountLine")}: </span>
                    {formatBrl(`-${item.cnpj_discount_amount}`, locale)}
                  </span>
                ) : null}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="grid gap-2 py-6 text-sm">
          {hasCnpjDiscount ? (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t("ordering.listSubtotal")}</span>
              <span className="text-muted-foreground">
                {formatBrl(order.list_subtotal ?? "0.00", locale)}
              </span>
            </div>
          ) : null}
          {hasCnpjDiscount ? (
            <div className="flex justify-between" data-testid="order-cnpj-discount-line">
              <span className="text-muted-foreground">{t("ordering.cnpjDiscountLine")}</span>
              <span className="text-success">{formatBrl(`-${cnpjDiscountTotal}`, locale)}</span>
            </div>
          ) : null}
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.subtotal")}</span>
            <span>{formatBrl(order.subtotal, locale)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.discountTotal")}</span>
            <span>{formatBrl(order.discount_total, locale)}</span>
          </div>
          {order.coupon_code && Number(order.coupon_discount_amount ?? "0") > 0 ? (
            <div className="flex justify-between" data-testid="order-coupon-line">
              <span className="text-muted-foreground">
                {t("ordering.coupon.orderCoupon", { code: order.coupon_code })}
              </span>
              <span className="text-success">
                {formatBrl(`-${order.coupon_discount_amount}`, locale)}
              </span>
            </div>
          ) : null}
          {Number(order.shipping_discount_amount ?? "0") > 0 ? (
            <div className="flex justify-between" data-testid="order-shipping-discount-line">
              <span className="text-muted-foreground">
                {t("ordering.coupon.orderShippingDiscount", {
                  code: order.coupon_code ?? "—",
                })}
              </span>
              <span className="text-success">
                {formatBrl(`-${order.shipping_discount_amount}`, locale)}
              </span>
            </div>
          ) : null}
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.shippingTotal")}</span>
            <span>{formatBrl(order.shipping_total, locale)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.taxTotal")}</span>
            <span>{formatBrl(order.tax_total, locale)}</span>
          </div>
          {hasCnpjDiscount ? (
            <div className="flex justify-between rounded-lg bg-success/10 px-3 py-2 text-success">
              <span className="text-xs font-semibold">{t("ordering.cnpjSavings")}</span>
              <span className="text-sm font-bold">{formatBrl(cnpjDiscountTotal, locale)}</span>
            </div>
          ) : null}
          <div className="flex justify-between border-t pt-2 text-base font-semibold">
            <span>{t("ordering.total")}</span>
            <PriceDisplay
              amount={order.total}
              primary="brl"
              showSecondary
              className="text-end text-base font-semibold"
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{t("ordering.createdAt")}</span>
            <span>{formatDate(order.created_at, locale)}</span>
          </div>
        </CardContent>
      </Card>

      {cancellable ? (
        <div className="flex justify-end">
          <Button
            variant="destructive"
            className="rounded-xl"
            disabled={cancelMutation.isPending}
            onClick={() => cancelMutation.mutate(order.id)}
          >
            {cancelMutation.isPending ? t("loading") : t("ordering.cancelOrder")}
          </Button>
        </div>
      ) : (
        <p className="text-end text-sm text-muted-foreground">{t("ordering.notCancellable")}</p>
      )}
    </div>
  );
}
