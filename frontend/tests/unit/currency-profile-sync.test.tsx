// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { buildCurrencyBootstrap, type FxRatesSnapshot } from "@/core/domain/currency";
import { CurrencyProfileSync } from "@/features/currency/currency-profile-sync";
import { accountApi } from "@/infrastructure/http";
import { CurrencyProvider, useCurrency } from "@/shared/components/currency-provider";
import { useAuthStore } from "@/shared/stores/auth-store";

const SNAPSHOT: FxRatesSnapshot = {
  rates: { BRL: "1", USD: "0.18408" },
  rateDate: "2026-10-30",
  source: "Frankfurter / European Central Bank",
  stale: false,
};

const SESSION = {
  access_token: "access-token",
  refresh_token: "refresh-token",
  token_type: "Bearer",
  expires_in: 3600,
  user: {
    id: "user-1",
    email: "buyer@example.com",
    full_name: "Comprador",
    role: "BUYER" as const,
    account_type: "COMPANY" as const,
  },
};

function SwitchButton() {
  const { setCurrency } = useCurrency();
  return (
    <button type="button" onClick={() => setCurrency("USD")}>
      Trocar para USD
    </button>
  );
}

function renderSync() {
  return render(
    <CurrencyProvider initial={buildCurrencyBootstrap("BRL", SNAPSHOT)}>
      <CurrencyProfileSync />
      <SwitchButton />
    </CurrencyProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  useAuthStore.setState({ session: null, status: "unauthenticated" });
});

describe("CurrencyProfileSync", () => {
  it("persiste a troca no perfil quando autenticado", async () => {
    useAuthStore.setState({ session: SESSION, status: "authenticated" });
    const persist = vi
      .spyOn(accountApi, "updatePreferences")
      .mockResolvedValue({ display_currency: "USD" });

    renderSync();
    fireEvent.click(screen.getByRole("button", { name: "Trocar para USD" }));

    await waitFor(() => {
      expect(persist).toHaveBeenCalledWith("access-token", "USD");
    });
  });

  it("não chama o perfil quando anônimo", async () => {
    useAuthStore.setState({ session: null, status: "unauthenticated" });
    const persist = vi.spyOn(accountApi, "updatePreferences");

    renderSync();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Trocar para USD" }));
      await Promise.resolve();
    });

    expect(persist).not.toHaveBeenCalled();
  });
});
