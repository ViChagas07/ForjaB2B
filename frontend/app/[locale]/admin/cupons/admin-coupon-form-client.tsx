"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowLeft, Loader2, Power } from "lucide-react";

import { CouponStatusBadge } from "@/features/admin/coupons/coupon-status-badge";
import { CouponForm } from "@/features/admin/coupons/coupon-form";
import {
  couponStatus,
  formatDateOnly,
  formatDiscountedAmount,
  formatPercentValue,
  redemptionStatusLabelKey,
  typeLongLabelKey,
} from "@/features/admin/coupons/display";
import {
  useAdminCoupon,
  useCreateCoupon,
  useGenerateCouponCode,
  useToggleCoupon,
  useUpdateCoupon,
} from "@/features/admin/coupons/hooks";
import {
  couponCreateFormSchema,
  couponEditFormSchema,
  couponFormFromDetail,
  EMPTY_COUPON_FORM,
  formErrors,
  toCouponCreate,
  toCouponUpdate,
  type CouponFormValues,
} from "@/features/admin/coupons/schemas";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/infrastructure/http";
import { formatDate } from "@/shared/lib/money";
import { useAuthStore } from "@/shared/stores/auth-store";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
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

function submitErrorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return "form.errorConflict";
    if (error.status === 422) return "form.errorValidation";
  }
  return "form.errorGeneric";
}

function toggleErrorKey(error: unknown): string {
  return error instanceof ApiError && error.status === 409
    ? "form.errorConflict"
    : "form.errorGeneric";
}

export function AdminCouponFormClient({ couponId }: { couponId: string | null }) {
  const t = useTranslations("admin.coupons");
  const router = useRouter();
  const session = useAuthStore((state) => state.session);
  const authStatus = useAuthStore((state) => state.status);

  const isEdit = Boolean(couponId);
  const couponQuery = useAdminCoupon(couponId);
  const createMutation = useCreateCoupon();
  const updateMutation = useUpdateCoupon(couponId ?? undefined);
  const generateMutation = useGenerateCouponCode();
  const toggleMutation = useToggleCoupon();

  const [values, setValues] = useState<CouponFormValues>(EMPTY_COUPON_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successKey, setSuccessKey] = useState<string | null>(null);
  const [toggleOpen, setToggleOpen] = useState(false);
  const [toggleError, setToggleError] = useState<string | null>(null);

  useEffect(() => {
    if (couponQuery.data) {
      setValues(couponFormFromDetail(couponQuery.data));
    }
  }, [couponQuery.data]);

  const isAdmin = session?.user.role === "ADMIN";

  if (authStatus === "idle" || (isEdit && couponQuery.isLoading)) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-80 w-full rounded-2xl" />
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

  if (isEdit && couponQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("loadError")}</AlertTitle>
        <AlertDescription>
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => void couponQuery.refetch()}
          >
            {t("retry")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const coupon = couponQuery.data;
  if (isEdit && !coupon) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{t("notFound")}</AlertDescription>
      </Alert>
    );
  }

  const lockIdentity = (coupon?.total_uses ?? 0) > 0 || (coupon?.last_redemptions.length ?? 0) > 0;
  const isSaving = createMutation.isPending || updateMutation.isPending;

  function updateField(patch: Partial<CouponFormValues>) {
    setValues((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      if (Object.keys(patch).length === 0) return current;
      const next = { ...current };
      for (const key of Object.keys(patch)) delete next[key];
      return next;
    });
    setSuccessKey(null);
    setSubmitError(null);
  }

  function validate(): boolean {
    const schema = isEdit ? couponEditFormSchema : couponCreateFormSchema;
    const result = schema.safeParse(values);
    if (result.success) {
      setErrors({});
      return true;
    }
    setErrors(formErrors(result));
    return false;
  }

  function handleSubmit() {
    if (!validate()) return;
    setSubmitError(null);
    setSuccessKey(null);
    if (isEdit && couponId) {
      updateMutation.mutate(toCouponUpdate(values), {
        onSuccess: () => {
          setSuccessKey("form.successUpdated");
        },
        onError: (error) => setSubmitError(submitErrorKey(error)),
      });
      return;
    }
    createMutation.mutate(toCouponCreate(values), {
      onSuccess: (created) => {
        router.push(`/admin/cupons/${created.id}`);
      },
      onError: (error) => setSubmitError(submitErrorKey(error)),
    });
  }

  function handleGenerateCode() {
    generateMutation.mutate(undefined, {
      onSuccess: (data) => updateField({ code: data.code }),
      onError: () => setSubmitError("form.errorGeneric"),
    });
  }

  function confirmToggle() {
    if (!coupon) return;
    setToggleError(null);
    toggleMutation.mutate(
      { couponId: coupon.id, isActive: !coupon.is_active },
      {
        onSuccess: () => {
          setToggleOpen(false);
          setSuccessKey(coupon.is_active ? "form.deactivatedSuccess" : "form.activatedSuccess");
        },
        onError: (error) => setToggleError(toggleErrorKey(error)),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link
            href="/admin/cupons"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft aria-hidden="true" className="h-3.5 w-3.5" />
            {t("detail.back")}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-black tracking-tight sm:text-3xl">
              {coupon ? coupon.code : t("form.newTitle")}
            </h1>
            {coupon ? <CouponStatusBadge status={couponStatus(coupon)} /> : null}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {coupon
              ? `${t(typeLongLabelKey(coupon.type))} · ${formatPercentValue(coupon.percent)}`
              : t("form.subtitle")}
          </p>
        </div>
        {coupon ? (
          <Button
            variant={coupon.is_active ? "outline" : "default"}
            onClick={() => {
              setToggleError(null);
              setToggleOpen(true);
            }}
          >
            <Power aria-hidden="true" className="h-4 w-4" />
            {coupon.is_active ? t("deactivate") : t("activate")}
          </Button>
        ) : null}
      </div>

      {coupon ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("detail.totalUses")}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-black tabular-nums">
                {coupon.total_uses}
                {coupon.usage_limit_total !== null ? ` / ${coupon.usage_limit_total}` : ""}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("detail.totalDiscounted")}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-black tabular-nums">
                {formatDiscountedAmount(coupon.total_discounted)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("table.validity")}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {coupon.valid_from
                  ? `${t("detail.from")} ${formatDateOnly(coupon.valid_from)}`
                  : null}
                {coupon.valid_from && coupon.valid_until ? " · " : null}
                {coupon.valid_until
                  ? `${t("detail.until")} ${formatDateOnly(coupon.valid_until)}`
                  : null}
                {!coupon.valid_from && !coupon.valid_until ? t("detail.always") : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t("detail.recentTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
              {coupon.last_redemptions.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("detail.noRedemptions")}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[620px] text-sm">
                    <thead className="border-b text-start text-xs uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th className="px-2 py-2 text-start">{t("detail.order")}</th>
                        <th className="px-2 py-2 text-start">{t("detail.company")}</th>
                        <th className="px-2 py-2 text-start">{t("detail.amount")}</th>
                        <th className="px-2 py-2 text-start">{t("detail.status")}</th>
                        <th className="px-2 py-2 text-start">{t("detail.date")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coupon.last_redemptions.map((redemption) => (
                        <tr key={redemption.id} className="border-b last:border-0">
                          <td className="px-2 py-2 font-mono text-xs">
                            {redemption.order_id.slice(0, 8)}
                          </td>
                          <td className="px-2 py-2 font-mono text-xs">
                            {redemption.company_id.slice(0, 8)}
                          </td>
                          <td className="px-2 py-2 tabular-nums">
                            {formatDiscountedAmount(redemption.amount_discounted)}
                          </td>
                          <td className="px-2 py-2">
                            {t(redemptionStatusLabelKey(redemption.status))}
                          </td>
                          <td className="px-2 py-2 text-xs text-muted-foreground">
                            {formatDate(redemption.created_at, "pt-BR")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}

      <CouponForm
        mode={isEdit ? "edit" : "create"}
        values={values}
        errors={errors}
        onChange={updateField}
        onSubmit={handleSubmit}
        isSaving={isSaving}
        isGeneratingCode={generateMutation.isPending}
        onGenerateCode={handleGenerateCode}
        lockIdentity={lockIdentity}
        submitErrorKey={submitError}
        successKey={successKey}
      />

      <Dialog open={toggleOpen} onOpenChange={setToggleOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {coupon?.is_active ? t("confirmDeactivateTitle") : t("confirmActivateTitle")}
            </DialogTitle>
            <DialogDescription>
              {coupon
                ? t(
                    coupon.is_active
                      ? "confirmDeactivateDescription"
                      : "confirmActivateDescription",
                    { code: coupon.code },
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
              onClick={() => setToggleOpen(false)}
              disabled={toggleMutation.isPending}
            >
              {t("cancel")}
            </Button>
            <Button
              variant={coupon?.is_active ? "destructive" : "default"}
              onClick={confirmToggle}
              disabled={toggleMutation.isPending}
            >
              {toggleMutation.isPending ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : null}
              {coupon?.is_active ? t("deactivate") : t("activate")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
