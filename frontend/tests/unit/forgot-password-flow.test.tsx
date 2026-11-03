// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/infrastructure/http";
import { ForgotPasswordFlow } from "@/features/auth/forgot-password-flow";

const mocks = vi.hoisted(() => ({
  request: vi.fn(),
  verify: vi.fn(),
  reset: vi.fn(),
}));

vi.mock("@/infrastructure/http", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/infrastructure/http")>();
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      requestPasswordRecovery: mocks.request,
      verifyPasswordRecovery: mocks.verify,
      resetPassword: mocks.reset,
    },
  };
});

vi.mock("@/features/auth/turnstile-widget", () => ({
  TurnstileWidget: ({ onToken }: { onToken: (token: string) => void }) => (
    <button type="button" data-testid="turnstile" onClick={() => onToken("turnstile-token")}>
      turnstile
    </button>
  ),
}));

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

function renderFlow() {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <ForgotPasswordFlow siteKey="test-site-key" nonce="nonce" />
    </NextIntlClientProvider>,
  );
}

function clickTurnstile() {
  fireEvent.click(screen.getByTestId("turnstile"));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ForgotPasswordFlow", () => {
  it("desabilita o outro campo e permite trocar de metodo", () => {
    renderFlow();
    const email = screen.getByLabelText("E-mail") as HTMLInputElement;
    const phone = screen.getByLabelText("Telefone") as HTMLInputElement;

    fireEvent.change(email, { target: { value: "user@example.com" } });

    expect(phone.disabled).toBe(true);
    expect(phone.value).toBe("");

    fireEvent.click(screen.getByRole("button", { name: "Usar telefone" }));

    expect(email.value).toBe("");
    expect(email.disabled).toBe(false);
    expect(phone.disabled).toBe(false);
  });

  it("segue request, verify e reset com resposta generica", async () => {
    mocks.request.mockResolvedValue(undefined);
    mocks.verify.mockResolvedValue({ reset_token: "reset-opaco", expires_in: 600 });
    mocks.reset.mockResolvedValue(undefined);
    renderFlow();

    fireEvent.change(screen.getByLabelText("E-mail"), {
      target: { value: " User@Example.COM " },
    });
    clickTurnstile();
    fireEvent.click(screen.getByRole("button", { name: "Enviar código" }));

    await waitFor(() => expect(mocks.request).toHaveBeenCalledTimes(1));
    expect(mocks.request.mock.calls[0]?.[0]).toMatchObject({
      email: "user@example.com",
      turnstile_token: "turnstile-token",
      locale: "pt-BR",
    });
    expect(await screen.findByText("Se os dados estiverem corretos, enviaremos um código.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Código de verificação"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Verificar código" }));

    await waitFor(() => expect(mocks.verify).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("heading", { name: "Defina uma nova senha" })).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Nova senha"), {
      target: { value: "SenhaNova123" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar nova senha"), {
      target: { value: "SenhaNova123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));

    await waitFor(() => expect(mocks.reset).toHaveBeenCalledTimes(1));
    expect(mocks.reset.mock.calls[0]?.[0]).toEqual({
      reset_token: "reset-opaco",
      new_password: "SenhaNova123",
    });
    expect(await screen.findByRole("heading", { name: "Senha alterada" })).toBeTruthy();
  });

  it("mostra Retry-After de 429 no pedido", async () => {
    mocks.request.mockRejectedValue(
      new ApiError(
        {
          type: "urn:forja:problem:rate_limit_exceeded",
          title: "Too Many Requests",
          status: 429,
        },
        { "retry-after": "30" },
      ),
    );
    renderFlow();

    fireEvent.change(screen.getByLabelText("E-mail"), {
      target: { value: "user@example.com" },
    });
    clickTurnstile();
    fireEvent.click(screen.getByRole("button", { name: "Enviar código" }));

    expect(await screen.findByText("Muitas tentativas. Aguarde 30s.")).toBeTruthy();
  });

  it("avisa sobre reuso de senha e oferece reiniciar", async () => {
    mocks.request.mockResolvedValue(undefined);
    mocks.verify.mockResolvedValue({ reset_token: "reset-opaco", expires_in: 600 });
    mocks.reset.mockRejectedValue(
      new ApiError({
        type: "urn:forja:problem:password_reuse",
        title: "Bad Request",
        status: 400,
      }),
    );
    renderFlow();

    fireEvent.change(screen.getByLabelText("E-mail"), {
      target: { value: "user@example.com" },
    });
    clickTurnstile();
    fireEvent.click(screen.getByRole("button", { name: "Enviar código" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("Código de verificação"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Verificar código" }));
    await waitFor(() => expect(mocks.verify).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("Nova senha"), {
      target: { value: "SenhaNova123" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar nova senha"), {
      target: { value: "SenhaNova123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));

    expect(await screen.findByText(/Recomece o processo/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Recomeçar" })).toBeTruthy();
  });
});

describe("ForgotPasswordFlow cooldown", () => {
  it("mostra contagem de 60s apos pedir o codigo", async () => {
    mocks.request.mockResolvedValue(undefined);
    renderFlow();

    fireEvent.change(screen.getByLabelText("E-mail"), {
      target: { value: "user@example.com" },
    });
    clickTurnstile();
    fireEvent.click(screen.getByRole("button", { name: "Enviar código" }));

    const resend = await screen.findByRole("button", { name: "Reenviar em 60s" });
    expect((resend as HTMLButtonElement).disabled).toBe(true);
  });
});
