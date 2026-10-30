import { describe, expect, it } from "vitest";

import {
  couponCreateFormSchema,
  couponEditFormSchema,
  EMPTY_COUPON_FORM,
  toCouponCreate,
  toCouponUpdate,
  type CouponFormValues,
} from "@/features/admin/coupons/schemas";

function values(overrides: Partial<CouponFormValues> = {}): CouponFormValues {
  return {
    ...EMPTY_COUPON_FORM,
    code: "FORJA-ABC123",
    percent: "15.00",
    ...overrides,
  };
}

describe("validação do formulário de cupom", () => {
  it("aceita o formulário de criação com código vazio", () => {
    expect(couponCreateFormSchema.safeParse(values({ code: "" })).success).toBe(true);
  });

  it("exige código na edição", () => {
    const result = couponEditFormSchema.safeParse(values({ code: "" }));
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe("validation.codeRequired");
    }
  });

  it("rejeita percentual fora de 0,01–100", () => {
    for (const percent of ["0", "100.01", "abc"]) {
      expect(couponCreateFormSchema.safeParse(values({ percent })).success).toBe(false);
    }
  });

  it("aceita os limites do percentual e vírgula decimal", () => {
    expect(couponCreateFormSchema.safeParse(values({ percent: "0.01" })).success).toBe(true);
    expect(couponCreateFormSchema.safeParse(values({ percent: "100" })).success).toBe(true);
    expect(couponCreateFormSchema.safeParse(values({ percent: "12,5" })).success).toBe(true);
  });

  it("rejeita código fora do formato", () => {
    for (const code of ["AB", "COM ESPAÇO", "PONTO.10"]) {
      expect(couponCreateFormSchema.safeParse(values({ code })).success).toBe(false);
    }
  });

  it("rejeita validade final anterior/igual à inicial", () => {
    const result = couponCreateFormSchema.safeParse(
      values({
        valid_from: "2026-11-30T10:00",
        valid_until: "2026-11-30T10:00",
      }),
    );
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((issue) => issue.message === "validation.dateOrder")).toBe(
        true,
      );
    }
  });

  it("rejeita limite zero e empresa inválida", () => {
    expect(couponCreateFormSchema.safeParse(values({ usage_limit_total: "0" })).success).toBe(
      false,
    );
    expect(couponCreateFormSchema.safeParse(values({ restricted_company_id: "abc" })).success).toBe(
      false,
    );
  });

  it("converte para payload de criação normalizando código e datas", () => {
    const payload = toCouponCreate(
      values({
        code: "  forja-abc123 ",
        valid_from: "2026-11-30T10:00",
        max_discount_amount: "50.00",
      }),
    );
    expect(payload.code).toBe("FORJA-ABC123");
    expect(payload.type).toBe("PRODUCT_TOTAL");
    expect(payload.percent).toBe("15.00");
    expect(payload.max_discount_amount).toBe("50.00");
    expect(payload.valid_from).toContain("2026-11-30");
  });

  it("normaliza vírgula decimal no payload", () => {
    const payload = toCouponCreate(values({ percent: "12,5", max_discount_amount: "50,25" }));
    expect(payload.percent).toBe("12.5");
    expect(payload.max_discount_amount).toBe("50.25");
  });

  it("converte PATCH limpando opcionais vazios", () => {
    const payload = toCouponUpdate(values({ max_discount_amount: "" }));
    expect(payload.code).toBe("FORJA-ABC123");
    expect(payload.max_discount_amount).toBeNull();
    expect(payload.usage_limit_total).toBeNull();
  });
});
