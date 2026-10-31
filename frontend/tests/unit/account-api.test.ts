import { afterEach, describe, expect, it, vi } from "vitest";

import { accountApi } from "@/infrastructure/http";

const TOKEN = "account-token";
const PROFILE = {
  id: "u-1",
  email: "buyer@example.com",
  full_name: "Comprador",
  phone: "+55 11 99999-9999",
  birth_date: "1990-01-01",
  gender: "MASCULINO",
  postal_code: "01310100",
  display_currency: "BRL",
  avatar_url: null,
  account_type: "COMPANY",
  role: "BUYER",
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("accountApi", () => {
  it("lê o perfil autenticado", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(PROFILE));
    vi.stubGlobal("fetch", fetchMock);

    const profile = await accountApi.get(TOKEN);

    expect(profile.postal_code).toBe("01310100");
    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/account");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer account-token");
  });

  it("atualiza via PATCH", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ ...PROFILE, full_name: "Novo Nome" }));
    vi.stubGlobal("fetch", fetchMock);

    await accountApi.update(TOKEN, {
      full_name: "Novo Nome",
      phone: null,
      birth_date: null,
      gender: null,
      postal_code: "01310100",
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/account");
    expect(init?.method).toBe("PATCH");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      full_name: "Novo Nome",
      postal_code: "01310100",
    });
  });

  it("persiste a moeda de exibicao em PATCH /account/preferences", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ display_currency: "USD" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await accountApi.updatePreferences(TOKEN, "USD");

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/account/preferences");
    expect(init?.method).toBe("PATCH");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer account-token");
    expect(JSON.parse(String(init?.body))).toEqual({ display_currency: "USD" });
    expect(result.display_currency).toBe("USD");
  });

  it("envia o avatar como corpo binario em PUT /account/avatar", async () => {
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "avatar.png", {
      type: "image/png",
    });
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        avatar_url: "/api/v1/account/avatar/company/user/key",
        updated_at: "2026-10-31T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await accountApi.uploadAvatar(TOKEN, file);

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/account/avatar");
    expect(init?.method).toBe("PUT");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("image/png");
    expect(init?.body).toBe(file);
    expect(result.avatar_url).toContain("/api/v1/account/avatar/");
  });

  it("remove o avatar em DELETE /account/avatar", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ avatar_url: null, updated_at: null }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await accountApi.removeAvatar(TOKEN);

    const [, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(init?.method).toBe("DELETE");
    expect(result.avatar_url).toBeNull();
  });
});
