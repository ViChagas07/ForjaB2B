"use client";

import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  House,
  Package,
  ReceiptText,
  TicketPercent,
  Trash2,
  Truck,
  Warehouse,
  Wallet,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import type { AvailableCoupon, Order } from "@/core/domain/ordering";
import { useAccount, useUpdateSpendingVisibility } from "@/features/account/hooks";
import { useCustomerOverview, useDeleteOrder } from "@/features/ordering";
import { deliveryStage, isCancelledStatus, orderStatusLabelKey } from "@/features/ordering/status";
import { Link } from "@/i18n/navigation";
import { PriceDisplay } from "@/shared/components/price-display";
import { errorMessageKey } from "@/shared/lib/api-error";
import { cn } from "@/shared/lib/utils";
import { formatBrl, formatDate, formatDateOnly, formatNumber } from "@/shared/lib/money";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Skeleton } from "@/shared/ui/skeleton";

const DELIVERY_STEPS = [
  { key: "stagePreparing", icon: Package },
  { key: "stageAtCarrier", icon: Warehouse },
  { key: "stageInTransit", icon: Truck },
  { key: "stageDelivered", icon: House },
] as const;

function statusVariant(
  status: string,
): "default" | "secondary" | "success" | "info" | "warning" | "danger" {
  if (status === "DELIVERED") return "success";
  if (status === "IN_TRANSIT") return "info";
  if (status === "CANCELLED" || status === "CREDIT_REJECTED") return "danger";
  if (status === "INVOICED" || status === "PAID") return "default";
  return "warning";
}

function orderCode(id: string): string {
  return id.slice(0, 8).toUpperCase();
}

function HiddenAmount({ label }: { label: string }) {
  return (
    <span className="tracking-[0.2em]" aria-label={label}>
      <span aria-hidden="true">••••••</span>
    </span>
  );
}

interface DeliveryRouteItemProps {
  order: Order;
  onDelete: (order: Order) => void;
  isDeleting: boolean;
}

function DeliveryRouteItem({ order, onDelete, isDeleting }: DeliveryRouteItemProps) {
  const t = useTranslations();
  const locale = useLocale();
  const stage = order.status === "RECEIVED" ? 3 : deliveryStage(order.status);
  const stopped = isCancelledStatus(order.status);

  return (
    <li className="py-5 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Link
            href={`/orders/${order.id}`}
            className="font-semibold text-forge-700 hover:underline dark:text-forge-300"
          >
            {t("ordering.orderNumber")} #{orderCode(order.id)}
          </Link>
          <span className="text-muted-foreground">{formatDate(order.created_at, locale)}</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(order.status)}>
            {t(orderStatusLabelKey(order.status))}
          </Badge>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
            aria-label={t("dashboard.deleteDelivery")}
            title={t("dashboard.deleteDelivery")}
            disabled={isDeleting}
            onClick={() => onDelete(order)}
          >
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
      <div className="mt-4">
        {stopped || stage === null ? (
          <Alert variant="destructive">
            <AlertDescription>{t("dashboard.deliveryStopped")}</AlertDescription>
          </Alert>
        ) : (
          <ol className="grid grid-cols-4 gap-1">
            {DELIVERY_STEPS.map((step, index) => {
              const Icon = step.icon;
              const completed = index < stage;
              const current = index === stage;
              return (
                <li key={step.key} className="relative flex flex-col items-center text-center">
                  {index > 0 ? (
                    <span
                      aria-hidden="true"
                      className={cn(
                        "absolute start-0 top-4 h-0.5 w-1/2 -translate-x-1/2 rtl:translate-x-1/2",
                        index <= stage ? "bg-primary" : "bg-border",
                      )}
                    />
                  ) : null}
                  {index < DELIVERY_STEPS.length - 1 ? (
                    <span
                      aria-hidden="true"
                      className={cn(
                        "absolute end-0 top-4 h-0.5 w-1/2 translate-x-1/2 rtl:-translate-x-1/2",
                        index < stage ? "bg-primary" : "bg-border",
                      )}
                    />
                  ) : null}
                  <span
                    className={cn(
                      "relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 bg-card transition-colors",
                      completed
                        ? "border-primary bg-primary text-primary-foreground"
                        : current
                          ? "border-primary text-primary ring-4 ring-primary/15"
                          : "border-border text-muted-foreground",
                    )}
                  >
                    {completed ? (
                      <Check aria-hidden="true" className="h-4 w-4" />
                    ) : (
                      <Icon aria-hidden="true" className="h-4 w-4" />
                    )}
                  </span>
                  <span
                    className={cn(
                      "mt-2 text-[11px] font-medium leading-tight",
                      current ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {t(`dashboard.${step.key}`)}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </li>
  );
}

interface DeliveryRoutesProps {
  orders: Order[];
  onDelete: (order: Order) => void;
  isDeleting: boolean;
}

function DeliveryRoutes({ orders, onDelete, isDeleting }: DeliveryRoutesProps) {
  const t = useTranslations();

  return (
    <Card className="rounded-2xl">
      <CardHeader>
        <CardTitle className="text-lg">{t("dashboard.deliveryTitle")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("dashboard.deliverySubtitleAll")}</p>
      </CardHeader>
      <CardContent>
        {orders.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-center">
            <p className="text-sm font-semibold">{t("dashboard.deliveryEmpty")}</p>
          </div>
        ) : (
          <ul className="divide-y">
            {orders.map((order) => (
              <DeliveryRouteItem
                key={order.id}
                order={order}
                onDelete={onDelete}
                isDeleting={isDeleting}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function CouponCard({ coupon }: { coupon: AvailableCoupon }) {
  const t = useTranslations();
  const locale = useLocale();
  const percent = formatNumber(Number(coupon.percent), locale);
  const label =
    coupon.type === "SHIPPING"
      ? t("dashboard.couponShipping", { percent })
      : t("dashboard.couponProduct", { percent });

  return (
    <li className="rounded-xl border border-dashed border-primary/35 bg-primary/[0.04] p-4">
      <div className="flex items-center justify-between gap-3">
        <code className="rounded-md bg-ink px-2.5 py-1 text-xs font-bold tracking-[0.14em] text-white">
          {coupon.code}
        </code>
        <TicketPercent aria-hidden="true" className="h-4 w-4 text-primary" />
      </div>
      <p className="mt-3 text-sm font-semibold">{label}</p>
      {typeof coupon.remaining_uses === "number" ? (
        <p className="mt-1 inline-flex rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
          {t("dashboard.couponRemaining", {
            count: formatNumber(coupon.remaining_uses, locale),
          })}
        </p>
      ) : null}
      <div className="mt-1 space-y-0.5 text-xs text-muted-foreground">
        {coupon.min_order_amount ? (
          <p>
            {t("dashboard.couponMinOrder", {
              amount: formatBrl(coupon.min_order_amount, locale),
            })}
          </p>
        ) : null}
        {coupon.valid_until ? (
          <p>
            {t("dashboard.couponValidUntil", {
              date: formatDateOnly(coupon.valid_until, locale),
            })}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function CouponsBoard({ coupons }: { coupons: AvailableCoupon[] }) {
  const t = useTranslations();

  return (
    <Card className="rounded-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <TicketPercent aria-hidden="true" className="h-5 w-5 text-primary" />
          {t("dashboard.couponsTitle")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("dashboard.couponsSubtitle")}</p>
      </CardHeader>
      <CardContent>
        {coupons.length === 0 ? (
          <div className="rounded-xl border border-dashed p-6 text-center">
            <p className="text-sm font-semibold">{t("dashboard.couponsEmpty")}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t("dashboard.couponsEmptyHint")}</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {coupons.map((coupon) => (
              <CouponCard key={coupon.code} coupon={coupon} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

interface OrderHistoryProps {
  orders: Order[];
  hideSpending: boolean;
  onDelete: (order: Order) => void;
  isDeleting: boolean;
}

function OrderHistory({ orders, hideSpending, onDelete, isDeleting }: OrderHistoryProps) {
  const t = useTranslations();
  const locale = useLocale();

  return (
    <Card className="rounded-2xl">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ReceiptText aria-hidden="true" className="h-5 w-5 text-primary" />
            {t("dashboard.ordersTitle")}
          </CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">{t("dashboard.ordersSubtitle")}</p>
        </div>
        <Button asChild variant="outline" size="sm" className="rounded-lg">
          <Link href="/catalog">
            {t("dashboard.browseCatalog")}
            <ArrowRight aria-hidden="true" className="rtl:-scale-x-100" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {orders.length === 0 ? (
          <div className="rounded-xl border border-dashed p-8 text-center">
            <Package aria-hidden="true" className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="mt-3 text-sm font-semibold">{t("dashboard.ordersEmpty")}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t("dashboard.ordersEmptyHint")}</p>
            <Button asChild size="sm" className="mt-4 rounded-lg">
              <Link href="/catalog">{t("dashboard.browseCatalog")}</Link>
            </Button>
          </div>
        ) : (
          <ul className="divide-y">
            {orders.map((order) => {
              const totalItems = order.items.reduce((sum, item) => sum + item.quantity, 0);
              return (
                <li key={order.id} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <Link
                        href={`/orders/${order.id}`}
                        className="font-semibold text-forge-700 hover:underline dark:text-forge-300"
                      >
                        #{orderCode(order.id)}
                      </Link>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatDate(order.created_at, locale)} ·{" "}
                        {t("cart.itemsCount", { count: totalItems })}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={statusVariant(order.status)}>
                        {t(orderStatusLabelKey(order.status))}
                      </Badge>
                      <div className="text-right text-sm font-bold">
                        {hideSpending ? (
                          <HiddenAmount label={t("dashboard.spendingHidden")} />
                        ) : (
                          <PriceDisplay amount={order.total} primary="brl" />
                        )}
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        aria-label={t("dashboard.deleteOrder")}
                        title={t("dashboard.deleteOrder")}
                        disabled={isDeleting}
                        onClick={() => onDelete(order)}
                      >
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </div>
                  </div>
                  {order.items.length > 0 ? (
                    <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                      {order.items
                        .map((item) => `${item.quantity}× ${item.product_name}`)
                        .join(" · ")}
                    </p>
                  ) : null}
                  <Link
                    href={`/orders/${order.id}`}
                    className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-forge-700 hover:underline dark:text-forge-300"
                  >
                    {t("dashboard.viewOrder")}
                    <ArrowRight aria-hidden="true" className="h-3 w-3 rtl:-scale-x-100" />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function StatCard({
  icon: Icon,
  label,
  children,
}: {
  icon: typeof Wallet;
  label: string;
  children: ReactNode;
}) {
  return (
    <Card className="rounded-2xl">
      <CardContent className="p-5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {label}
          </span>
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon aria-hidden="true" className="h-4 w-4" />
          </span>
        </div>
        <div className="mt-4">{children}</div>
      </CardContent>
    </Card>
  );
}

export function CustomerDashboard() {
  const t = useTranslations();
  const locale = useLocale();
  const accountQuery = useAccount();
  const overviewQuery = useCustomerOverview(200);
  const updateVisibility = useUpdateSpendingVisibility();
  const deleteOrder = useDeleteOrder();
  const [pendingDelete, setPendingDelete] = useState<Order | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function requestDelete(order: Order) {
    setDeleteError(null);
    setPendingDelete(order);
  }

  function closeDeleteDialog() {
    if (deleteOrder.isPending) {
      return;
    }
    setPendingDelete(null);
    setDeleteError(null);
  }

  function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    deleteOrder.mutate(pendingDelete.id, {
      onSuccess: () => {
        setPendingDelete(null);
        setDeleteError(null);
      },
      onError: (error) => {
        setDeleteError(t(errorMessageKey(error)));
      },
    });
  }

  if (overviewQuery.isLoading || accountQuery.isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    );
  }

  if (overviewQuery.isError || !overviewQuery.data) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
          {t("dashboard.loadError")}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void overviewQuery.refetch()}
          >
            {t("dashboard.retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const overview = overviewQuery.data;
  const hideSpending = accountQuery.data?.hide_spending ?? false;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-3">
        <StatCard icon={Wallet} label={t("dashboard.totalSpent")}>
          <div className="flex items-end justify-between gap-2">
            <p className="text-2xl font-black tracking-tight">
              {hideSpending ? (
                <HiddenAmount label={t("dashboard.spendingHidden")} />
              ) : (
                <PriceDisplay amount={overview.total_spent} primary="brl" />
              )}
            </p>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => updateVisibility.mutate(!hideSpending)}
              disabled={updateVisibility.isPending || accountQuery.isLoading}
              aria-label={hideSpending ? t("dashboard.showSpending") : t("dashboard.hideSpending")}
              title={hideSpending ? t("dashboard.showSpending") : t("dashboard.hideSpending")}
            >
              {hideSpending ? (
                <Eye aria-hidden="true" className="h-4 w-4" />
              ) : (
                <EyeOff aria-hidden="true" className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{t("dashboard.spendingHint")}</p>
        </StatCard>

        <StatCard icon={ReceiptText} label={t("dashboard.ordersStat")}>
          <p className="text-2xl font-black tracking-tight">
            {formatNumber(overview.orders_count, locale)}
          </p>
        </StatCard>

        <StatCard icon={TicketPercent} label={t("dashboard.couponsStat")}>
          <p className="text-2xl font-black tracking-tight">
            {formatNumber(overview.coupons.length, locale)}
          </p>
        </StatCard>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <DeliveryRoutes
          orders={overview.orders}
          onDelete={requestDelete}
          isDeleting={deleteOrder.isPending}
        />
        <CouponsBoard coupons={overview.coupons} />
      </div>

      <OrderHistory
        orders={overview.orders}
        hideSpending={hideSpending}
        onDelete={requestDelete}
        isDeleting={deleteOrder.isPending}
      />

      <Dialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeDeleteDialog();
          }
        }}
      >
        <DialogContent className="max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>{t("dashboard.deleteConfirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("dashboard.deleteConfirmDescription", {
                code: pendingDelete ? orderCode(pendingDelete.id) : "",
              })}
            </DialogDescription>
          </DialogHeader>
          {deleteError ? (
            <Alert variant="destructive">
              <AlertDescription>{deleteError}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              disabled={deleteOrder.isPending}
              onClick={closeDeleteDialog}
            >
              {t("dashboard.deleteCancel")}
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="rounded-xl"
              disabled={deleteOrder.isPending}
              onClick={confirmDelete}
            >
              {deleteOrder.isPending ? t("dashboard.deleting") : t("dashboard.deleteConfirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
