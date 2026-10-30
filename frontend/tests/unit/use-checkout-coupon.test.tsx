// @vitest-environment jsdom
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthSession } from "@/core/domain/auth";
import { useCheckoutCoupon } from "@/features/ordering/use-checkout-coupon";
import { ApiError } from "@/infrastructure/http";
import { createQueryClient } from "@/shared/lib/query-client";
import { useAuthStore } from "@/shared/stores/auth-store";

const SESSION: AuthSession = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
  user: {
    id: "user-1",
    email: "a@b.com",
    full_name: "A",
    role: "BUYER",
    account_type: "COMPANY",
  },
};

function preview(overrides: Record<string, unknown> = {}) {
  return {
    valid: true,
    reason: null,
    missing_amount: null,
    subtotal: "100.00",
    recovery_discount: "0.00",
    coupon_discount: "0.00",
    shipping_discount: "0.00",
    shipping_total: "25.00",
    pix_discount: "0.00",
    total: "125.00",
    applied_discounts: [],
    currency: "BRL",
    ...overrides,
  };
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function makeWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <NextIntlClientProvider locale="pt-BR" messages={{}}>
          {children}
        </NextIntlClientProvider>
      </QueryClientProvider>
    );
  };
}

beforeEach(() => {
  useAuthStore.getState().setSession(SESSION);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  useAuthStore.setState({ session: null, status: "idle" });
});

describe("useCheckoutCoupon", () => {
  it("aplica código válido e revalida quando o pagamento muda", async () => {
    const fetchMock = vi.fn<typeof fetch>((_input, init) => {
      const body = JSON.parse(String(init?.body)) as {
        code: string | null;
        payment_method: string;
      };
      if (body.payment_method === "BOLETO" && body.code) {
        return Promise.resolve(
          jsonResponse(
            preview({
              valid: false,
              reason: "EXPIRED",
              total: null,
            }),
          ),
        );
      }
      if (body.code) {
        return Promise.resolve(
          jsonResponse(
            preview({
              coupon_discount: "10.00",
              total: "115.00",
              applied_discounts: ["COUPON_PRODUCT"],
            }),
          ),
        );
      }
      return Promise.resolve(jsonResponse(preview()));
    });
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      (props: { paymentMethod: "PIX" | "BOLETO" }) =>
        useCheckoutCoupon({
          paymentMethod: props.paymentMethod,
          cartSignature: "cart-1",
          hasItems: true,
          orderError: null,
        }),
      { wrapper: makeWrapper(queryClient), initialProps: { paymentMethod: "PIX" } },
    );

    await waitFor(() => expect(result.current.preview?.total).toBe("125.00"));

    act(() => result.current.setInput("cupom10"));
    act(() => result.current.apply());

    await waitFor(() => expect(result.current.appliedCode).toBe("CUPOM10"));
    expect(result.current.preview?.total).toBe("115.00");

    rerender({ paymentMethod: "BOLETO" });

    await waitFor(() => expect(result.current.error?.reason).toBe("EXPIRED"));
    expect(result.current.appliedCode).toBeNull();
    expect(result.current.expanded).toBe(true);
  });

  it("mantém erro tipado ao aplicar cupom inválido", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockImplementation(() =>
        Promise.resolve(
          jsonResponse(
            preview({
              valid: false,
              reason: "NOT_FOUND",
              subtotal: null,
              shipping_total: null,
              total: null,
            }),
          ),
        ),
      ),
    );

    const queryClient = createQueryClient();
    const { result } = renderHook(
      () =>
        useCheckoutCoupon({
          paymentMethod: "PIX",
          cartSignature: "cart-1",
          hasItems: true,
          orderError: null,
        }),
      { wrapper: makeWrapper(queryClient) },
    );
    act(() => result.current.setInput("NAO-EXISTE"));
    act(() => result.current.apply());

    await waitFor(() => expect(result.current.error?.reason).toBe("NOT_FOUND"));
    expect(result.current.appliedCode).toBeNull();
  });

  it("remove o cupom aplicado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockImplementation((_input, init) => {
        const body = JSON.parse(String(init?.body)) as { code: string | null };
        return Promise.resolve(
          jsonResponse(
            body.code ? preview({ coupon_discount: "10.00", total: "115.00" }) : preview(),
          ),
        );
      }),
    );

    const queryClient = createQueryClient();
    const { result } = renderHook(
      () =>
        useCheckoutCoupon({
          paymentMethod: "PIX",
          cartSignature: "cart-1",
          hasItems: true,
          orderError: null,
        }),
      { wrapper: makeWrapper(queryClient) },
    );
    act(() => result.current.setInput("CUPOM10"));
    act(() => result.current.apply());
    await waitFor(() => expect(result.current.appliedCode).toBe("CUPOM10"));

    act(() => result.current.remove());
    expect(result.current.appliedCode).toBeNull();
    expect(result.current.input).toBe("");
  });

  it("expõe erro de cupom devolvido na criação do pedido", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockImplementation(() => Promise.resolve(jsonResponse(preview()))),
    );
    const orderError = new ApiError({
      type: "urn:forja:problem:coupon_expired",
      title: "Unprocessable Entity",
      status: 422,
    });

    const queryClient = createQueryClient();
    const { result } = renderHook(
      () =>
        useCheckoutCoupon({
          paymentMethod: "PIX",
          cartSignature: "cart-1",
          hasItems: true,
          orderError,
        }),
      { wrapper: makeWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.error?.reason).toBe("EXPIRED"));
    expect(result.current.expanded).toBe(true);
  });
});
