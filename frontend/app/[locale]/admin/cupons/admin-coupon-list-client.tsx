"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight, Loader2, MoreHorizontal, Plus, Search } from "lucide-react";

import type { AdminCoupon, AdminCouponListQuery, CouponFilterStatus } from "@/core/domain/coupons";
import { CouponStatusBadge } from "@/features/admin/coupons/coupon-status-badge";
import {
  couponStatus,
  formatCouponUsage,
  formatCouponValidity,
  formatPercentValue,
  typeLabelKey,
} from "@/features/admin/coupons/display";
import { useAdminCoupons, useToggleCoupon } from "@/features/admin/coupons/hooks";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/infrastructure/http";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";

type PendingToggle = {
  coupon: AdminCoupon;
  nextActive: boolean;
};

function toggleErrorKey(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return "form.errorConflict";
  }
  return "form.errorGeneric";
}

export function AdminCouponListClient() {
  const t = useTranslations("admin.coupons");
  const session = useAuthStore((state) => state.session);
  const status = useAuthStore((state) => state.status);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<CouponFilterStatus | "ALL">("ALL");
  const [page, setPage] = useState(1);
  const [noticeKey, setNoticeKey] = useState<string | null>(null);
  const [pendingToggle, setPendingToggle] = useState<PendingToggle | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  const filters: AdminCouponListQuery = {
    q: query || undefined,
    status: filterStatus === "ALL" ? undefined : filterStatus,
    page,
    page_size: 20,
  };
  const couponsQuery = useAdminCoupons(filters);
  const toggleMutation = useToggleCoupon();

  const isAdmin = session?.user.role === "ADMIN";

  if (status === "idle") {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <Card className="mx-auto w-full max-w-md">
        <CardHeader>
          <CardTitle>{t("accessDenied")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="destructive">
            <AlertDescription>{t("adminOnly")}</AlertDescription>
          </Alert>
          <Button asChild className="w-full">
            <Link href="/dashboard">{t("backToDashboard")}</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const data = couponsQuery.data;
  const items = data?.items ?? [];

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    setQuery(searchInput.trim());
    setPage(1);
  }

  function changeStatus(value: string) {
    setFilterStatus(value as CouponFilterStatus | "ALL");
    setPage(1);
  }

  function openToggle(coupon: AdminCoupon) {
    setToggleError(null);
    setPendingToggle({ coupon, nextActive: !coupon.is_active });
  }

  function confirmToggle() {
    if (!pendingToggle) return;
    setToggleError(null);
    toggleMutation.mutate(
      {
        couponId: pendingToggle.coupon.id,
        isActive: pendingToggle.nextActive,
      },
      {
        onSuccess: () => {
          setNoticeKey(
            pendingToggle.nextActive ? "form.activatedSuccess" : "form.deactivatedSuccess",
          );
          setPendingToggle(null);
        },
        onError: (error) => setToggleError(toggleErrorKey(error)),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight sm:text-3xl">{t("title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button asChild>
          <Link href="/admin/cupons/new">
            <Plus aria-hidden="true" className="h-4 w-4" />
            {t("newCoupon")}
          </Link>
        </Button>
      </div>

      {noticeKey ? (
        <Alert variant="success">
          <AlertDescription>{t(noticeKey)}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardContent className="space-y-4 p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <form onSubmit={submitSearch} className="flex flex-1 gap-2">
              <Input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder={t("searchPlaceholder")}
                aria-label={t("searchPlaceholder")}
              />
              <Button type="submit" variant="outline" size="icon">
                <Search aria-hidden="true" className="h-4 w-4" />
              </Button>
            </form>
            <Select value={filterStatus} onValueChange={changeStatus}>
              <SelectTrigger className="sm:w-56" aria-label={t("allStatuses")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">{t("allStatuses")}</SelectItem>
                <SelectItem value="ACTIVE">{t("status.active")}</SelectItem>
                <SelectItem value="EXPIRED">{t("status.expired")}</SelectItem>
                <SelectItem value="EXHAUSTED">{t("status.exhausted")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {couponsQuery.isLoading ? (
            <div className="space-y-2 py-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : couponsQuery.isError ? (
            <Alert variant="destructive">
              <AlertTitle>{t("loadError")}</AlertTitle>
              <AlertDescription>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => void couponsQuery.refetch()}
                >
                  {t("retry")}
                </Button>
              </AlertDescription>
            </Alert>
          ) : items.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">{t("noResults")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead className="border-b text-start text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-3 text-start">{t("table.code")}</th>
                    <th className="px-2 py-3 text-start">{t("table.type")}</th>
                    <th className="px-2 py-3 text-start">{t("table.percent")}</th>
                    <th className="px-2 py-3 text-start">{t("table.validity")}</th>
                    <th className="px-2 py-3 text-start">{t("table.usage")}</th>
                    <th className="px-2 py-3 text-start">{t("table.status")}</th>
                    <th className="px-2 py-3 text-end">{t("table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((coupon) => (
                    <tr key={coupon.id} className="border-b last:border-0">
                      <td className="px-2 py-3 font-mono font-semibold">
                        <Link
                          href={`/admin/cupons/${coupon.id}`}
                          className="underline-offset-4 hover:underline"
                        >
                          {coupon.code}
                        </Link>
                      </td>
                      <td className="px-2 py-3">
                        <Badge variant="outline">{t(typeLabelKey(coupon.type))}</Badge>
                      </td>
                      <td className="px-2 py-3 tabular-nums">
                        {formatPercentValue(coupon.percent)}
                      </td>
                      <td className="px-2 py-3">{formatCouponValidity(coupon)}</td>
                      <td className="px-2 py-3 tabular-nums">{formatCouponUsage(coupon)}</td>
                      <td className="px-2 py-3">
                        <CouponStatusBadge status={couponStatus(coupon)} />
                      </td>
                      <td className="px-2 py-3 text-end">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" aria-label={t("actions")}>
                              <MoreHorizontal aria-hidden="true" className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem asChild>
                              <Link href={`/admin/cupons/${coupon.id}`}>{t("edit")}</Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => openToggle(coupon)}>
                              {coupon.is_active ? t("deactivate") : t("activate")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.pages > 1 ? (
            <div className="flex items-center justify-between gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft aria-hidden="true" className="h-4 w-4" />
                {t("previous")}
              </Button>
              <span className="text-xs text-muted-foreground">
                {t("pageInfo", {
                  page: data.page,
                  pages: data.pages,
                  total: data.total,
                })}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage((current) => current + 1)}
              >
                {t("next")}
                <ChevronRight aria-hidden="true" className="h-4 w-4" />
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Dialog
        open={Boolean(pendingToggle)}
        onOpenChange={(open) => {
          if (!open) setPendingToggle(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pendingToggle?.nextActive ? t("confirmActivateTitle") : t("confirmDeactivateTitle")}
            </DialogTitle>
            <DialogDescription>
              {pendingToggle
                ? t(
                    pendingToggle.nextActive
                      ? "confirmActivateDescription"
                      : "confirmDeactivateDescription",
                    { code: pendingToggle.coupon.code },
                  )
                : null}
            </DialogDescription>
          </DialogHeader>
          {toggleError ? (
            <Alert variant="destructive">
              <AlertDescription>{t(toggleError)}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPendingToggle(null)}
              disabled={toggleMutation.isPending}
            >
              {t("cancel")}
            </Button>
            <Button
              variant={pendingToggle?.nextActive ? "default" : "destructive"}
              onClick={confirmToggle}
              disabled={toggleMutation.isPending}
            >
              {toggleMutation.isPending ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : null}
              {pendingToggle?.nextActive ? t("activate") : t("deactivate")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
