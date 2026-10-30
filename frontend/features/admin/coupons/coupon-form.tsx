"use client";

import { ChevronDown, Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

import type { CouponType } from "@/core/domain/coupons";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Checkbox } from "@/shared/ui/checkbox";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";

import { CouponSummary } from "./coupon-summary";
import type { CouponFormValues } from "./schemas";

const QUICK_PERCENTS = [5, 10, 15, 20] as const;

interface CouponFormProps {
  mode: "create" | "edit";
  values: CouponFormValues;
  errors: Record<string, string>;
  onChange: (patch: Partial<CouponFormValues>) => void;
  onSubmit: () => void;
  isSaving: boolean;
  isGeneratingCode: boolean;
  onGenerateCode: () => void;
  lockIdentity: boolean;
  submitErrorKey: string | null;
  successKey: string | null;
}

function fieldError(
  t: ReturnType<typeof useTranslations>,
  errors: Record<string, string>,
  field: keyof CouponFormValues,
) {
  const key = errors[field];
  if (!key) return null;
  return (
    <p className="text-xs text-destructive" role="alert">
      {t(key)}
    </p>
  );
}

export function CouponForm({
  mode,
  values,
  errors,
  onChange,
  onSubmit,
  isSaving,
  isGeneratingCode,
  onGenerateCode,
  lockIdentity,
  submitErrorKey,
  successKey,
}: CouponFormProps) {
  const t = useTranslations("admin.coupons");

  return (
    <Card className="rounded-2xl">
      <CardHeader>
        <CardTitle>{t(mode === "create" ? "form.newTitle" : "form.editTitle")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("form.subtitle")}</p>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-6"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          {successKey ? (
            <Alert variant="success">
              <AlertDescription>{t(successKey)}</AlertDescription>
            </Alert>
          ) : null}
          {submitErrorKey ? (
            <Alert variant="destructive">
              <AlertDescription>{t(submitErrorKey)}</AlertDescription>
            </Alert>
          ) : null}
          {Object.keys(errors).length > 0 ? (
            <Alert variant="destructive">
              <AlertDescription>{t("form.errorValidation")}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="coupon-code">{t("form.code")} *</Label>
              <div className="flex gap-2">
                <Input
                  id="coupon-code"
                  value={values.code}
                  disabled={lockIdentity}
                  maxLength={32}
                  placeholder={t("form.codePlaceholder")}
                  aria-invalid={Boolean(errors.code)}
                  onChange={(event) => onChange({ code: event.target.value.toUpperCase() })}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="shrink-0"
                  disabled={lockIdentity || isGeneratingCode}
                  onClick={onGenerateCode}
                >
                  {isGeneratingCode ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles aria-hidden="true" className="h-4 w-4" />
                  )}
                  {isGeneratingCode ? t("form.generating") : t("form.generateCode")}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">{t("form.codeHint")}</p>
              {fieldError(t, errors, "code")}
              {lockIdentity ? (
                <p className="text-xs text-warning">{t("form.identityLocked")}</p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="coupon-type">{t("form.type")} *</Label>
              <Select
                value={values.type}
                disabled={lockIdentity}
                onValueChange={(value) => onChange({ type: value as CouponType })}
              >
                <SelectTrigger id="coupon-type" aria-invalid={Boolean(errors.type)}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="PRODUCT_TOTAL">{t("type.productLong")}</SelectItem>
                  <SelectItem value="SHIPPING">{t("type.shippingLong")}</SelectItem>
                </SelectContent>
              </Select>
              {fieldError(t, errors, "type")}
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <Label htmlFor="coupon-percent">{t("form.percent")} *</Label>
              <Input
                id="coupon-percent"
                inputMode="decimal"
                value={values.percent}
                placeholder="0,00"
                aria-invalid={Boolean(errors.percent)}
                onChange={(event) => onChange({ percent: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">{t("form.percentHint")}</p>
              {fieldError(t, errors, "percent")}
            </div>
            <div className="space-y-2">
              <span className="text-xs font-medium text-muted-foreground">
                {t("form.quickPercent")}
              </span>
              <div className="flex flex-wrap gap-2">
                {QUICK_PERCENTS.map((value) => (
                  <Button
                    key={value}
                    type="button"
                    variant={values.percent === String(value) ? "default" : "outline"}
                    size="sm"
                    onClick={() => onChange({ percent: String(value) })}
                  >
                    {value}%
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <CouponSummary values={values} />

          <details className="group rounded-xl border bg-muted/20">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold [&::-webkit-details-marker]:hidden">
              {t("form.advanced")}
              <ChevronDown
                aria-hidden="true"
                className="h-4 w-4 transition-transform group-open:rotate-180"
              />
            </summary>
            <div className="grid gap-5 border-t px-4 py-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="coupon-valid-from">{t("form.validFrom")}</Label>
                <Input
                  id="coupon-valid-from"
                  type="datetime-local"
                  value={values.valid_from}
                  aria-invalid={Boolean(errors.valid_from)}
                  onChange={(event) => onChange({ valid_from: event.target.value })}
                />
                {fieldError(t, errors, "valid_from")}
              </div>
              <div className="space-y-2">
                <Label htmlFor="coupon-valid-until">{t("form.validUntil")}</Label>
                <Input
                  id="coupon-valid-until"
                  type="datetime-local"
                  value={values.valid_until}
                  aria-invalid={Boolean(errors.valid_until)}
                  onChange={(event) => onChange({ valid_until: event.target.value })}
                />
                {fieldError(t, errors, "valid_until")}
              </div>
              <div className="space-y-2">
                <Label htmlFor="coupon-limit-total">{t("form.usageLimitTotal")}</Label>
                <Input
                  id="coupon-limit-total"
                  inputMode="numeric"
                  value={values.usage_limit_total}
                  aria-invalid={Boolean(errors.usage_limit_total)}
                  onChange={(event) => onChange({ usage_limit_total: event.target.value })}
                />
                {fieldError(t, errors, "usage_limit_total")}
              </div>
              <div className="space-y-2">
                <Label htmlFor="coupon-limit-company">{t("form.usageLimitPerCompany")}</Label>
                <Input
                  id="coupon-limit-company"
                  inputMode="numeric"
                  value={values.usage_limit_per_company}
                  aria-invalid={Boolean(errors.usage_limit_per_company)}
                  onChange={(event) => onChange({ usage_limit_per_company: event.target.value })}
                />
                {fieldError(t, errors, "usage_limit_per_company")}
              </div>
              <div className="space-y-2">
                <Label htmlFor="coupon-min-order">{t("form.minOrder")}</Label>
                <Input
                  id="coupon-min-order"
                  inputMode="decimal"
                  value={values.min_order_amount}
                  aria-invalid={Boolean(errors.min_order_amount)}
                  onChange={(event) => onChange({ min_order_amount: event.target.value })}
                />
                {fieldError(t, errors, "min_order_amount")}
              </div>
              <div className="space-y-2">
                <Label htmlFor="coupon-max-discount">{t("form.maxDiscount")}</Label>
                <Input
                  id="coupon-max-discount"
                  inputMode="decimal"
                  value={values.max_discount_amount}
                  aria-invalid={Boolean(errors.max_discount_amount)}
                  onChange={(event) => onChange({ max_discount_amount: event.target.value })}
                />
                {fieldError(t, errors, "max_discount_amount")}
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="coupon-company">{t("form.restrictedCompany")}</Label>
                <Input
                  id="coupon-company"
                  value={values.restricted_company_id}
                  placeholder="00000000-0000-0000-0000-000000000000"
                  aria-invalid={Boolean(errors.restricted_company_id)}
                  onChange={(event) => onChange({ restricted_company_id: event.target.value })}
                />
                {fieldError(t, errors, "restricted_company_id")}
              </div>
              <div className="flex items-center gap-3 md:col-span-2">
                <Checkbox
                  id="coupon-active"
                  checked={values.is_active}
                  onChange={(event) => onChange({ is_active: event.target.checked })}
                />
                <Label htmlFor="coupon-active">{t("form.active")}</Label>
              </div>
            </div>
          </details>

          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button type="submit" disabled={isSaving} className="min-w-40">
              {isSaving ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : null}
              {isSaving
                ? t(mode === "create" ? "form.creating" : "form.saving")
                : t(mode === "create" ? "form.create" : "form.save")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
