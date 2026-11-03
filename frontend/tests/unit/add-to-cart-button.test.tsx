// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AddToCartButton } from "@/features/cart/add-to-cart-button";

const mocks = vi.hoisted(() => ({
  mutate: vi.fn(),
}));

vi.mock("@/features/cart/hooks", () => ({
  useAddCartItem: () => ({ mutate: mocks.mutate, isPending: false }),
}));

vi.mock("@/shared/stores/auth-store", () => ({
  useAuthStore: (selector: (state: { status: string }) => unknown) =>
    selector({ status: "authenticated" }),
}));

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function renderButton() {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <AddToCartButton productId="p-1" minQuantity={2} />
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
  mocks.mutate.mockImplementation((_input: unknown, options?: { onSuccess?: () => void }) =>
    options?.onSuccess?.(),
  );
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("AddToCartButton", () => {
  it("confirma a adicao e volta ao estado normal apos 3 segundos", () => {
    renderButton();
    const button = screen.getByRole("button", { name: /adicionar ao carrinho/i });

    fireEvent.click(button);

    expect(mocks.mutate).toHaveBeenCalledWith(
      { product_id: "p-1", quantity: 2 },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(screen.getByRole("button", { name: /pedido adicionado ao carrinho/i })).toBeTruthy();
    expect(button.className).toContain("bg-success");

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByRole("button", { name: /adicionar ao carrinho/i })).toBeTruthy();
    expect(button.className).not.toContain("bg-success");
  });
});
