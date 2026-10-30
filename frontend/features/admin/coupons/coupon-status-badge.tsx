"use client";

import { useTranslations } from "next-intl";

import type { CouponStatus } from "@/core/domain/coupons";
import { Badge, type BadgeProps } from "@/shared/ui/badge";

import { statusLabelKey } from "./display";

const VARIANTS: Record<CouponStatus, NonNullable<BadgeProps["variant"]>> = {
  ACTIVE: "success",
  EXPIRED: "destructive",
  EXHAUSTED: "warning",
  INACTIVE: "secondary",
};

export function CouponStatusBadge({ status }: { status: CouponStatus }) {
  const t = useTranslations("admin.coupons");
  return <Badge variant={VARIANTS[status]}>{t(statusLabelKey(status))}</Badge>;
}
