import { describe, expect, it } from "vitest";

import type { AdminCoupon } from "@/core/domain/coupons";
import {
  buildCouponSummary,
  couponStatus,
  formatCouponUsage,
  formatCouponValidity,
  formatPercentValue,
} from "@/features/admin/coupons/display";

function coupon(overrides: Partial<AdminCoupon> = {}): AdminCoupon {
  return {
    id: "c-1",
    code: "FORJA-ABC123",
    type: "PRODUCT_TOTAL",
    percent: "15.00",
    max_discount_amount: null,
    min_order_amount: null,
    valid_from: null,
    valid_until: null,
    usage_limit_total: null,
    usage_limit_per_company: null,
    restricted_company_id: null,
    is_active: true,
    created_by: "u-1",
    created_at: "2026-10-30T12:00:00Z",
    updated_at: "2026-10-30T12:00:00Z",
    total_uses: 0,
    total_discounted: "0.00",
    ...overrides,
  };
}

describe("display de cupons", () => {
  it("deriva status inativo, expirado, esgotado e ativo", () => {
    const now = new Date("2026-10-30T12:00:00Z");
    expect(couponStatus(coupon({ is_active: false }), now)).toBe("INACTIVE");
    expect(couponStatus(coupon({ valid_until: "2026-10-29T12:00:00Z" }), now)).toBe("EXPIRED");
    expect(couponStatus(coupon({ usage_limit_total: 2, total_uses: 2 }), now)).toBe("EXHAUSTED");
    expect(couponStatus(coupon(), now)).toBe("ACTIVE");
  });

  it("formata usos com e sem limite", () => {
    expect(formatCouponUsage(coupon({ total_uses: 12 }))).toBe("12");
    expect(formatCouponUsage(coupon({ total_uses: 12, usage_limit_total: 50 }))).toBe("12/50");
  });

  it("formata percentual e validade", () => {
    expect(formatPercentValue("15.00")).toBe("15%");
    expect(
      formatCouponValidity(
        coupon({
          valid_from: "2026-11-01T12:00:00Z",
          valid_until: "2026-11-30T23:59:00Z",
        }),
      ),
    ).toContain("01/11/2026");
  });

  it("monta resumo natural com tipo, percentual, data e teto", () => {
    const summary = buildCouponSummary(
      {
        type: "SHIPPING",
        percent: "15",
        valid_from: "",
        valid_until: "2026-11-30T12:00:00Z",
        max_discount_amount: "50.00",
        min_order_amount: "",
        usage_limit_total: "",
        usage_limit_per_company: "",
      },
      (key, values) => `${key}|${JSON.stringify(values ?? {})}`,
    );
    expect(summary).toContain("form.summaryShipping");
    expect(summary).toContain('"percent":"15"');
    expect(summary).toContain("form.summaryUntil");
    expect(summary).toContain("form.summaryMax");
    expect(summary).toContain("R$");
  });
});
