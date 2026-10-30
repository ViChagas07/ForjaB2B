import * as z from "zod";

import {
  COUPON_TYPES,
  type AdminCoupon,
  type AdminCouponCreate,
  type AdminCouponUpdate,
  type CouponType,
} from "@/core/domain/coupons";
import { fromFormDateTime, toFormDateTime } from "./display";

const CODE_PATTERN = /^[A-Z0-9_-]{4,32}$/;
const MONEY_PATTERN = /^\d{1,12}([.,]\d{1,2})?$/;
const POSITIVE_INT_PATTERN = /^\d+$/;

export interface CouponFormValues {
  code: string;
  type: CouponType;
  percent: string;
  max_discount_amount: string;
  min_order_amount: string;
  valid_from: string;
  valid_until: string;
  usage_limit_total: string;
  usage_limit_per_company: string;
  restricted_company_id: string;
  is_active: boolean;
}

export const EMPTY_COUPON_FORM: CouponFormValues = {
  code: "",
  type: "PRODUCT_TOTAL",
  percent: "",
  max_discount_amount: "",
  min_order_amount: "",
  valid_from: "",
  valid_until: "",
  usage_limit_total: "",
  usage_limit_per_company: "",
  restricted_company_id: "",
  is_active: true,
};

export function couponFormFromDetail(coupon: AdminCoupon): CouponFormValues {
  return {
    code: coupon.code,
    type: coupon.type,
    percent: coupon.percent,
    max_discount_amount: coupon.max_discount_amount ?? "",
    min_order_amount: coupon.min_order_amount ?? "",
    valid_from: toFormDateTime(coupon.valid_from),
    valid_until: toFormDateTime(coupon.valid_until),
    usage_limit_total: coupon.usage_limit_total === null ? "" : String(coupon.usage_limit_total),
    usage_limit_per_company:
      coupon.usage_limit_per_company === null ? "" : String(coupon.usage_limit_per_company),
    restricted_company_id: coupon.restricted_company_id ?? "",
    is_active: coupon.is_active,
  };
}

function codeSchema(required: boolean) {
  return z
    .string()
    .trim()
    .max(32, "validation.codeInvalid")
    .refine((value) => !required || value.length > 0, "validation.codeRequired")
    .refine((value) => !value || CODE_PATTERN.test(value.toUpperCase()), "validation.codeInvalid");
}

function optionalMoney(positive: boolean) {
  return z
    .string()
    .trim()
    .refine((value) => !value || MONEY_PATTERN.test(value), "validation.amountInvalid")
    .refine((value) => {
      if (!value) return true;
      const amount = Number(value.replace(",", "."));
      return positive ? amount > 0 : amount >= 0;
    }, "validation.amountInvalid");
}

function optionalLimit() {
  return z
    .string()
    .trim()
    .refine(
      (value) => !value || (POSITIVE_INT_PATTERN.test(value) && Number(value) >= 1),
      "validation.limitInvalid",
    );
}

export function couponFormSchema(requireCode: boolean) {
  return z
    .object({
      code: codeSchema(requireCode),
      type: z.enum(COUPON_TYPES, {
        errorMap: () => ({ message: "validation.typeRequired" }),
      }),
      percent: z
        .string()
        .trim()
        .min(1, "validation.percentRequired")
        .refine(
          (value) =>
            MONEY_PATTERN.test(value) &&
            Number(value.replace(",", ".")) >= 0.01 &&
            Number(value.replace(",", ".")) <= 100,
          "validation.percentInvalid",
        ),
      max_discount_amount: optionalMoney(true),
      min_order_amount: optionalMoney(false),
      valid_from: z.string(),
      valid_until: z.string(),
      usage_limit_total: optionalLimit(),
      usage_limit_per_company: optionalLimit(),
      restricted_company_id: z
        .string()
        .trim()
        .refine(
          (value) =>
            !value || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value),
          "validation.companyInvalid",
        ),
      is_active: z.boolean(),
    })
    .superRefine((values: CouponFormValues, ctx) => {
      if (values.valid_from && values.valid_until) {
        const from = new Date(values.valid_from);
        const until = new Date(values.valid_until);
        if (!Number.isNaN(from.getTime()) && !Number.isNaN(until.getTime()) && until <= from) {
          ctx.addIssue({
            path: ["valid_until"],
            code: z.ZodIssueCode.custom,
            message: "validation.dateOrder",
          });
        }
      }
    });
}

export const couponCreateFormSchema = couponFormSchema(false);
export const couponEditFormSchema = couponFormSchema(true);

export function formErrors(
  result: z.SafeParseReturnType<CouponFormValues, CouponFormValues>,
): Record<string, string> {
  if (result.success) return {};
  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    const key = issue.path[0];
    if (typeof key === "string" && !errors[key]) {
      errors[key] = issue.message;
    }
  }
  return errors;
}

function optionalValue(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function optionalDecimal(value: string): string | null {
  const normalized = optionalValue(value);
  return normalized ? normalized.replace(",", ".") : null;
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

export function toCouponCreate(values: CouponFormValues): AdminCouponCreate {
  const code = values.code.trim().toUpperCase();
  return {
    ...(code ? { code } : {}),
    type: values.type,
    percent: values.percent.trim().replace(",", "."),
    max_discount_amount: optionalDecimal(values.max_discount_amount),
    min_order_amount: optionalDecimal(values.min_order_amount),
    valid_from: fromFormDateTime(values.valid_from),
    valid_until: fromFormDateTime(values.valid_until),
    usage_limit_total: optionalNumber(values.usage_limit_total),
    usage_limit_per_company: optionalNumber(values.usage_limit_per_company),
    restricted_company_id: optionalValue(values.restricted_company_id),
    is_active: values.is_active,
  };
}

export function toCouponUpdate(values: CouponFormValues): AdminCouponUpdate {
  return {
    code: values.code.trim().toUpperCase(),
    type: values.type,
    percent: values.percent.trim().replace(",", "."),
    max_discount_amount: optionalDecimal(values.max_discount_amount),
    min_order_amount: optionalDecimal(values.min_order_amount),
    valid_from: fromFormDateTime(values.valid_from),
    valid_until: fromFormDateTime(values.valid_until),
    usage_limit_total: optionalNumber(values.usage_limit_total),
    usage_limit_per_company: optionalNumber(values.usage_limit_per_company),
    restricted_company_id: optionalValue(values.restricted_company_id),
    is_active: values.is_active,
  };
}
