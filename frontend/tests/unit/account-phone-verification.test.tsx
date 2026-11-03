// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountClient } from "@/app/[locale]/account/account-client";

const mocks = vi.hoisted(() => ({
  start: vi.fn(),
  check: vi.fn(),
  status: { verified: false, phone_masked: null as string | null },
  profile: {
    id: "u-1",
    email: "buyer@example.com",
    full_name: "Comprador",
    phone: null,
    birth_date: null,
    gender: null,
    postal_code: null,
    display_currency: "BRL",
    avatar_url: null,
    account_type: "COMPANY",
    role: "BUYER",
    hide_spending: false,
  },
}));

vi.mock("@/features/account/hooks", () => ({
  useAccount: () => ({
    data: mocks.profile,
    isLoading: false,
    error: null,
  }),
  useUpdateAccount: () => ({ mutate: vi.fn(), isPending: false }),
  usePhoneVerificationStatus: () => ({ data: mocks.status, isLoading: false }),
  useStartPhoneVerification: () => ({
    mutate: (variables: unknown, options?: { onSuccess?: () => void }) => {
      mocks.start(variables);
      options?.onSuccess?.();
    },
    isPending: false,
  }),
  useCheckPhoneVerification: () => ({
    mutate: (variables: unknown, options?: { onSuccess?: () => void }) => {
      mocks.check(variables);
      options?.onSuccess?.();
    },
    isPending: false,
  }),
}));

vi.mock("@/features/account/avatar-card", () => ({
  AccountAvatarCard: () => null,
}));

vi.mock("@/shared/stores/auth-store", () => ({
  useAuthStore: (selector: (state: unknown) => unknown) =>
    selector({
      session: { user: { avatar_url: null } },
      status: "authenticated",
    }),
}));

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function renderAccount() {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <AccountClient />
    </NextIntlClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mocks.status = { verified: false, phone_masked: null };
});

describe("AccountClient phone verification", () => {
  it("abre o dialogo, envia o start e confirma o codigo", async () => {
    renderAccount();

    fireEvent.click(screen.getByRole("button", { name: "Verificar telefone" }));
    expect(screen.getByRole("heading", { name: "Verificar telefone" })).toBeTruthy();

    const phoneInputs = screen.getAllByLabelText("Telefone");
    fireEvent.change(phoneInputs[phoneInputs.length - 1] as HTMLInputElement, {
      target: { value: "+55 (11) 99999-1234" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar código" }));

    await waitFor(() => expect(mocks.start).toHaveBeenCalledTimes(1));
    expect(mocks.start.mock.calls[0]?.[0]).toEqual({
      phone: "+5511999991234",
      locale: "pt-BR",
    });
    expect(await screen.findByLabelText("Código SMS")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Código SMS"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(mocks.check).toHaveBeenCalledTimes(1));
    expect(mocks.check.mock.calls[0]?.[0]).toEqual({
      phone: "+5511999991234",
      code: "123456",
    });
    expect(await screen.findByText("Telefone verificado.")).toBeTruthy();
  });

  it("mostra o numero mascarado quando ja verificado", () => {
    mocks.status = { verified: true, phone_masked: "+55 ** *****-1234" };
    renderAccount();

    expect(screen.getByText("Verificado: +55 ** *****-1234")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Verificar telefone" })).toBeNull();
  });
});
