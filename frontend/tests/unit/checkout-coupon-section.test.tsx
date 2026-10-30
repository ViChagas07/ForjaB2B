// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import type * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CheckoutCouponSection } from "@/features/ordering/checkout-coupon-section";

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function renderSection(
  overrides: Partial<React.ComponentProps<typeof CheckoutCouponSection>> = {},
) {
  const props: React.ComponentProps<typeof CheckoutCouponSection> = {
    expanded: false,
    input: "",
    appliedCode: null,
    error: null,
    isLoading: false,
    isRevalidating: false,
    onToggle: vi.fn(),
    onInputChange: vi.fn(),
    onApply: vi.fn(),
    onRemove: vi.fn(),
    ...overrides,
  };
  render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <CheckoutCouponSection {...props} />
    </NextIntlClientProvider>,
  );
  return props;
}

afterEach(() => {
  cleanup();
});

describe("CheckoutCouponSection", () => {
  it("expande, foca o input e aplica com Enter", () => {
    const onToggle = vi.fn();
    const onApply = vi.fn();
    renderSection({ onToggle, onApply });

    fireEvent.click(screen.getByRole("button", { name: /Inserir código de cupom/ }));
    expect(onToggle).toHaveBeenCalledTimes(1);

    cleanup();
    renderSection({ expanded: true, input: "CUPOM10", onApply });
    const input = screen.getByLabelText("Cupom de desconto");
    expect(document.activeElement).toBe(input);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("mostra motivo específico e valor faltante", () => {
    renderSection({
      expanded: true,
      input: "CUPOM10",
      error: { reason: "MIN_ORDER_NOT_MET", missingAmount: "50.00" },
    });
    expect(screen.getByRole("alert").textContent).toMatch(/Faltam/);
    expect(screen.getByRole("alert").textContent).toMatch(/50,00/);
  });

  it("mostra erro de cupom expirado", () => {
    renderSection({
      expanded: true,
      error: { reason: "EXPIRED", missingAmount: null },
    });
    expect(screen.getByRole("alert").textContent).toContain("expirou");
  });

  it("mostra chip aplicado e remove", () => {
    const onRemove = vi.fn();
    renderSection({ appliedCode: "FORJA-ABC123", onRemove });
    expect(screen.getByText("FORJA-ABC123")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("aplicado");
    fireEvent.click(screen.getByRole("button", { name: "Remover cupom FORJA-ABC123" }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("exibe carregamento ao aplicar", () => {
    renderSection({ expanded: true, input: "X", isLoading: true });
    expect(screen.getByRole("button", { name: /Aplicando/ })).toBeTruthy();
  });

  it("renderiza o código como texto e não como HTML", () => {
    const payload = "<img src=x onerror=alert(1)>";
    renderSection({ appliedCode: payload });
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText(payload)).toBeTruthy();
  });
});
