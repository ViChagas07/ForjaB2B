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
});
