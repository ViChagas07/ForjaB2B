// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AccountProfile } from "@/core/domain/account";
import { AVATAR_MAX_BYTES } from "@/core/domain/avatar";
import { AccountAvatarCard } from "@/features/account/avatar-card";

const mocks = vi.hoisted(() => ({
  upload: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("@/features/account/hooks", () => ({
  useUploadAvatar: () => ({ mutate: mocks.upload, isPending: false }),
  useRemoveAvatar: () => ({ mutate: mocks.remove, isPending: false }),
}));

const messages = JSON.parse(
  readFileSync(join(process.cwd(), "messages", "pt-BR.json"), "utf-8"),
) as AbstractIntlMessages;

const PROFILE: AccountProfile = {
  id: "u-1",
  email: "buyer@example.com",
  full_name: "Comprador Teste",
  phone: null,
  birth_date: null,
  gender: null,
  postal_code: null,
  display_currency: "BRL",
  avatar_url: null,
  account_type: "COMPANY",
  role: "BUYER",
};

function renderCard(overrides: Partial<AccountProfile> = {}, fallback: string | null = null) {
  return render(
    <NextIntlClientProvider locale="pt-BR" messages={messages}>
      <AccountAvatarCard profile={{ ...PROFILE, ...overrides }} fallbackAvatarUrl={fallback} />
    </NextIntlClientProvider>,
  );
}

function fileInput(): HTMLInputElement {
  return screen.getByLabelText("Alterar foto") as HTMLInputElement;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AccountAvatarCard", () => {
  it("envia uma imagem valida para o hook de upload", () => {
    renderCard();
    const file = new File([new Uint8Array([1, 2, 3])], "avatar.png", { type: "image/png" });

    fireEvent.change(fileInput(), { target: { files: [file] } });

    expect(mocks.upload).toHaveBeenCalledTimes(1);
    expect(mocks.upload.mock.calls[0]?.[0]).toBe(file);
  });

  it("bloqueia formato nao suportado antes de chamar a API", () => {
    renderCard();
    const file = new File(["texto"], "avatar.txt", { type: "text/plain" });

    fireEvent.change(fileInput(), { target: { files: [file] } });

    expect(mocks.upload).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("JPG");
  });

  it("bloqueia imagem acima de 2 MB", () => {
    renderCard();
    const file = new File(["x"], "grande.png", { type: "image/png" });
    Object.defineProperty(file, "size", { value: AVATAR_MAX_BYTES + 1 });

    fireEvent.change(fileInput(), { target: { files: [file] } });

    expect(mocks.upload).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("2 MB");
  });

  it("mostra remover apenas quando existe avatar", () => {
    renderCard();
    expect(screen.queryByRole("button", { name: "Remover" })).toBeNull();

    cleanup();
    renderCard({ avatar_url: "/api/v1/account/avatar/c/u/k" });
    expect(screen.getByRole("button", { name: "Remover" })).toBeTruthy();
  });

  it("remove o avatar pelo hook", () => {
    renderCard({ avatar_url: "/api/v1/account/avatar/c/u/k" });

    fireEvent.click(screen.getByRole("button", { name: "Remover" }));

    expect(mocks.remove).toHaveBeenCalledTimes(1);
  });

  it("usa o avatar do provedor como fallback", () => {
    const { container } = renderCard({}, "https://lh3.googleusercontent.com/a/foto");

    expect(screen.getByRole("button", { name: "Remover" })).toBeTruthy();
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      "https://lh3.googleusercontent.com/a/foto",
    );
  });
});
