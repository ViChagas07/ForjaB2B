"use client";

import * as React from "react";
import { Loader2, Tag, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { formatBrl } from "@/shared/lib/money";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

import type { CouponUiError } from "./use-checkout-coupon";

interface CheckoutCouponSectionProps {
  expanded: boolean;
  input: string;
  appliedCode: string | null;
  error: CouponUiError | null;
  isLoading: boolean;
  isRevalidating: boolean;
  onToggle: () => void;
  onInputChange: (value: string) => void;
  onApply: () => void;
  onRemove: () => void;
}

function errorMessageKey(error: CouponUiError): string {
  if (error.reason === "CODE_REQUIRED") return "ordering.coupon.errors.codeRequired";
  if (error.reason === "GENERIC") return "ordering.coupon.errors.generic";
  if (error.reason === "MIN_ORDER_NOT_MET") {
    return error.missingAmount
      ? "ordering.coupon.errors.minOrderMissing"
      : "ordering.coupon.errors.minOrder";
  }
  return `ordering.coupon.errors.${error.reason}`;
}

export function CheckoutCouponSection({
  expanded,
  input,
  appliedCode,
  error,
  isLoading,
  isRevalidating,
  onToggle,
  onInputChange,
  onApply,
  onRemove,
}: CheckoutCouponSectionProps) {
  const t = useTranslations();
  const locale = useLocale();
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (expanded && !appliedCode) {
      inputRef.current?.focus();
    }
  }, [expanded, appliedCode]);

  if (appliedCode) {
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2">
          <Tag aria-hidden="true" className="h-4 w-4 shrink-0 text-primary" />
          <span className="text-xs font-semibold text-muted-foreground">
            {t("ordering.coupon.appliedShort")}
          </span>
          <span className="font-mono text-sm font-bold" dir="ltr">
            {appliedCode}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ms-auto h-7 px-2 text-xs"
            aria-label={t("ordering.coupon.removeAria", { code: appliedCode })}
            onClick={onRemove}
          >
            <X aria-hidden="true" className="h-3.5 w-3.5" />
            {t("ordering.coupon.remove")}
          </Button>
        </div>
        <p className="text-xs text-success" role="status" aria-live="polite">
          {t("ordering.coupon.applied", { code: appliedCode })}
        </p>
        {isRevalidating ? (
          <p
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
            role="status"
            aria-live="polite"
          >
            <Loader2 aria-hidden="true" className="h-3 w-3 animate-spin" />
            {t("ordering.coupon.revalidating")}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
        aria-expanded={expanded}
        aria-controls="checkout-coupon-fields"
        onClick={onToggle}
      >
        <Tag aria-hidden="true" className="h-4 w-4" />
        {t("ordering.coupon.insertCode")}
      </button>

      {expanded ? (
        <div id="checkout-coupon-fields" className="space-y-2">
          <Label htmlFor="checkout-coupon-code" className="text-xs">
            {t("ordering.coupon.label")}
          </Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              ref={inputRef}
              id="checkout-coupon-code"
              value={input}
              autoComplete="off"
              maxLength={32}
              dir="ltr"
              placeholder={t("ordering.coupon.placeholder")}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "checkout-coupon-error" : undefined}
              onChange={(event) => onInputChange(event.target.value.toUpperCase())}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onApply();
                }
              }}
            />
            <Button type="button" className="sm:w-auto" disabled={isLoading} onClick={onApply}>
              {isLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : null}
              {isLoading ? t("ordering.coupon.applying") : t("ordering.coupon.apply")}
            </Button>
          </div>
          {error ? (
            <p id="checkout-coupon-error" role="alert" className="text-xs text-destructive">
              {t(errorMessageKey(error), {
                amount: error.missingAmount != null ? formatBrl(error.missingAmount, locale) : "",
              })}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
