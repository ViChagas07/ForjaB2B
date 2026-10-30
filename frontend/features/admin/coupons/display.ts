import type { AdminCoupon, CouponStatus, CouponType } from "@/core/domain/coupons";
import { formatMoney } from "@/shared/lib/money";

const ADMIN_LOCALE = "pt-BR";

export interface CouponSummaryInput {
  type: CouponType;
  percent: string;
  valid_from: string;
  valid_until: string;
  max_discount_amount: string;
  min_order_amount: string;
  usage_limit_total: string;
  usage_limit_per_company: string;
}

export type CouponSummaryTranslate = (
  key: string,
  values?: Record<string, string | number>,
) => string;

export function couponStatus(coupon: AdminCoupon, now = new Date()): CouponStatus {
  if (!coupon.is_active) return "INACTIVE";
  if (coupon.valid_until) {
    const until = new Date(coupon.valid_until);
    if (!Number.isNaN(until.getTime()) && until <= now) return "EXPIRED";
  }
  if (coupon.usage_limit_total !== null && coupon.total_uses >= coupon.usage_limit_total) {
    return "EXHAUSTED";
  }
  return "ACTIVE";
}

export function statusLabelKey(status: CouponStatus): string {
  return `status.${status.toLowerCase()}`;
}

export function typeLabelKey(type: CouponType): string {
  return type === "SHIPPING" ? "type.shipping" : "type.product";
}

export function typeLongLabelKey(type: CouponType): string {
  return type === "SHIPPING" ? "type.shippingLong" : "type.productLong";
}

export function redemptionStatusLabelKey(status: string): string {
  return status === "RELEASED" ? "detail.released" : "detail.applied";
}

export function formatPercentNumber(value: string): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return new Intl.NumberFormat(ADMIN_LOCALE, {
    maximumFractionDigits: 2,
  }).format(number);
}

export function formatPercentValue(value: string): string {
  return `${formatPercentNumber(value)}%`;
}

export function formatDateOnly(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(ADMIN_LOCALE, { dateStyle: "short" }).format(date);
}

export function formatCouponValidity(coupon: AdminCoupon): string {
  if (!coupon.valid_from && !coupon.valid_until) return "—";
  if (coupon.valid_from && coupon.valid_until) {
    return `${formatDateOnly(coupon.valid_from)} – ${formatDateOnly(coupon.valid_until)}`;
  }
  if (coupon.valid_until) return `≤ ${formatDateOnly(coupon.valid_until)}`;
  return `≥ ${formatDateOnly(coupon.valid_from)}`;
}

export function formatCouponUsage(coupon: AdminCoupon): string {
  if (coupon.usage_limit_total === null) return String(coupon.total_uses);
  return `${coupon.total_uses}/${coupon.usage_limit_total}`;
}

export function formatDiscountedAmount(value: string): string {
  return formatMoney(value, "BRL", ADMIN_LOCALE);
}

export function buildCouponSummary(values: CouponSummaryInput, t: CouponSummaryTranslate): string {
  const parts: string[] = [
    t(values.type === "SHIPPING" ? "form.summaryShipping" : "form.summaryProduct", {
      percent: formatPercentNumber(values.percent || "0"),
    }),
  ];

  if (values.valid_until) {
    parts.push(t("form.summaryUntil", { date: formatDateOnly(values.valid_until) }));
  } else if (values.valid_from) {
    parts.push(t("form.summaryFrom", { date: formatDateOnly(values.valid_from) }));
  }

  if (values.max_discount_amount) {
    parts.push(
      t("form.summaryMax", {
        amount: formatMoney(values.max_discount_amount.replace(",", "."), "BRL", ADMIN_LOCALE),
      }),
    );
  }
  if (values.min_order_amount) {
    parts.push(
      t("form.summaryMin", {
        amount: formatMoney(values.min_order_amount.replace(",", "."), "BRL", ADMIN_LOCALE),
      }),
    );
  }
  if (values.usage_limit_total) {
    parts.push(
      t("form.summaryLimitTotal", {
        count: formatPercentNumber(values.usage_limit_total),
      }),
    );
  }
  if (values.usage_limit_per_company) {
    parts.push(
      t("form.summaryLimitCompany", {
        count: formatPercentNumber(values.usage_limit_per_company),
      }),
    );
  }

  return `${parts.join(", ")}.`;
}

export function toFormDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function fromFormDateTime(value: string): string | null {
  if (!value.trim()) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}
