import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, authApi } from "@/infrastructure/http";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authApi password recovery", () => {
  it("envia request generico com turnstile", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ status: "accepted" }, 202));
    vi.stubGlobal("fetch", fetchMock);

    await authApi.requestPasswordRecovery({
      email: "user@example.com",
      turnstile_token: "token",
      locale: "pt-BR",
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/auth/password-recovery/request");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      email: "user@example.com",
      turnstile_token: "token",
      locale: "pt-BR",
    });
  });

  it("verifica e devolve reset token", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ reset_token: "opaco", expires_in: 600 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await authApi.verifyPasswordRecovery({ phone: "+5511999991234", code: "123456" });

    expect(result.reset_token).toBe("opaco");
    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/auth/password-recovery/verify");
    expect(JSON.parse(String(init?.body))).toEqual({
      phone: "+5511999991234",
      code: "123456",
    });
  });

  it("faz reset com reset_token e nova senha", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await authApi.resetPassword({ reset_token: "opaco", new_password: "SenhaNova123" });

    const [url, init] = fetchMock.mock.calls[0] ?? [null, {}];
    expect(String(url)).toContain("/api/v1/auth/password-recovery/reset");
    expect(JSON.parse(String(init?.body))).toEqual({
      reset_token: "opaco",
      new_password: "SenhaNova123",
    });
  });

  it("expõe Retry-After em 429", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse(
          { type: "urn:forja:problem:rate_limit_exceeded", title: "Too Many", status: 429 },
          429,
          { "retry-after": "42" },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      authApi.requestPasswordRecovery({ email: "user@example.com", turnstile_token: "token" }),
    ).rejects.toMatchObject({ retryAfterSeconds: 42 });
  });
});

describe("authApi phone verification", () => {
  it("envia start/check e consulta status com bearer", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ status: "accepted" }, 202))
      .mockResolvedValueOnce(jsonResponse({ verified: true }))
      .mockResolvedValueOnce(jsonResponse({ verified: true, phone_masked: "+55 ** *****-1234" }));
    vi.stubGlobal("fetch", fetchMock);

    await authApi.startPhoneVerification("token", "+5511999991234", "pt-BR");
    await authApi.checkPhoneVerification("token", "+5511999991234", "123456");
    const status = await authApi.getPhoneVerificationStatus("token");

    expect(status.phone_masked).toBe("+55 ** *****-1234");
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls[0]).toContain("/api/v1/account/phone/verification/start");
    expect(urls[1]).toContain("/api/v1/account/phone/verification/check");
    expect(urls[2]).toContain("/api/v1/account/phone/verification");
    for (const [, init] of fetchMock.mock.calls) {
      expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer token");
    }
  });

  it("não vaza token em erro de rede", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      authApi.requestPasswordRecovery({ email: "user@example.com", turnstile_token: "segredo" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
