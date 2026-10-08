"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";

import { Link } from "@/i18n/navigation";
import type { OrderStatus } from "@/core/domain/ordering";
import { formatDate, formatMoney, DEFAULT_CURRENCY } from "@/shared/lib/money";
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

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/dashboard">
            <ArrowLeft aria-hidden="true" />
            {t("ordering.back")}
          </Link>
        </Button>
        <Badge variant={order.status === "CANCELLED" ? "destructive" : "default"}>
          {statusKey ? t(statusKey) : order.status}
        </Badge>
      </div>

      <h1 className="text-2xl font-semibold tracking-tight">
        {t("ordering.orderNumber")} <span className="font-mono">{order.id}</span>
      </h1>

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
            <div key={item.sku} className="flex items-center justify-between text-sm">
              <div>
                <span className="font-medium">{item.product_name}</span>
                <span className="text-muted-foreground">
                  {" "}
                  ({item.sku}) × {item.quantity}
                </span>
              </div>
              <span className="font-medium">
                {formatMoney(item.line_total, DEFAULT_CURRENCY, locale)}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="grid gap-2 py-6 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.subtotal")}</span>
            <span>{formatMoney(order.subtotal, DEFAULT_CURRENCY, locale)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.discountTotal")}</span>
            <span>{formatMoney(order.discount_total, DEFAULT_CURRENCY, locale)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.shippingTotal")}</span>
            <span>{formatMoney(order.shipping_total, DEFAULT_CURRENCY, locale)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("ordering.taxTotal")}</span>
            <span>{formatMoney(order.tax_total, DEFAULT_CURRENCY, locale)}</span>
          </div>
          <div className="flex justify-between border-t pt-2 text-base font-semibold">
            <span>{t("ordering.total")}</span>
            <span>{formatMoney(order.total, DEFAULT_CURRENCY, locale)}</span>
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
            disabled={cancelMutation.isPending}
            onClick={() => cancelMutation.mutate(order.id)}
          >
            {cancelMutation.isPending ? t("loading") : t("ordering.cancelOrder")}
          </Button>
        </div>
      ) : (
        <p className="text-right text-sm text-muted-foreground">{t("ordering.notCancellable")}</p>
      )}
    </div>
  );
}
