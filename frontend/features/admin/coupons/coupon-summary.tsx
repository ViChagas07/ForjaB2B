"use client";

import { useTranslations } from "next-intl";

import { buildCouponSummary, type CouponSummaryInput } from "./display";

export function CouponSummary({ values }: { values: CouponSummaryInput }) {
  const t = useTranslations("admin.coupons");
  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-foreground">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-primary">
        {t("form.summary")}
      </p>
      <p className="mt-1">{buildCouponSummary(values, t)}</p>
    </div>
  );
}
