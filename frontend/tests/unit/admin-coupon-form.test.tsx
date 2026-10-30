// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CouponForm } from "@/features/admin/coupons/coupon-form";
import { EMPTY_COUPON_FORM, type CouponFormValues } from "@/features/admin/coupons/schemas";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function Harness({ onSubmit }: { onSubmit: () => void }) {
  const [values, setValues] = React.useState<CouponFormValues>({
    ...EMPTY_COUPON_FORM,
    code: "FORJA-ABC123",
    type: "SHIPPING",
    percent: "15",
    valid_until: "2026-11-30T12:00:00Z",
    max_discount_amount: "50.00",
  });
  return (
    <CouponForm
      mode="create"
      values={values}
      errors={{}}
      onChange={(patch) => setValues((current) => ({ ...current, ...patch }))}
      onSubmit={onSubmit}
      isSaving={false}
      isGeneratingCode={false}
      onGenerateCode={vi.fn()}
      lockIdentity={false}
      submitErrorKey={null}
      successKey={null}
    />
  );
}

function renderForm(onSubmit = vi.fn()) {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <Harness onSubmit={onSubmit} />
    </NextIntlClientProvider>,
  );
}

afterEach(() => {
  cleanup();
});

describe("CouponForm", () => {
  it("mostra resumo natural e atalhos de percentual", () => {
    renderForm();
    expect(screen.getByText(/15% de desconto no frete/)).toBeTruthy();
    expect(screen.getByText(/válido até/)).toBeTruthy();
    expect(screen.getByText(/máx\./)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "10%" }));
    expect(screen.getByText(/10% de desconto no frete/)).toBeTruthy();
  });

  it("normaliza o código para maiúsculas e envia o formulário", () => {
    const onSubmit = vi.fn();
    renderForm(onSubmit);
    const code = screen.getByLabelText(/Código/) as HTMLInputElement;
    fireEvent.change(code, { target: { value: "forja-novo" } });
    expect(code.value).toBe("FORJA-NOVO");
    fireEvent.click(screen.getByRole("button", { name: /Criar cupom/ }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("aciona a geração de código", () => {
    const onGenerate = vi.fn();
    render(
      <NextIntlClientProvider locale="pt-BR" messages={messages}>
        <CouponForm
          mode="create"
          values={EMPTY_COUPON_FORM}
          errors={{}}
          onChange={vi.fn()}
          onSubmit={vi.fn()}
          isSaving={false}
          isGeneratingCode={false}
          onGenerateCode={onGenerate}
          lockIdentity={false}
          submitErrorKey={null}
          successKey={null}
        />
      </NextIntlClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Gerar código/ }));
    expect(onGenerate).toHaveBeenCalledTimes(1);
  });
});
