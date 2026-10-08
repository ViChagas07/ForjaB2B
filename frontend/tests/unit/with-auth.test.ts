import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthSession } from "@/core/domain/auth";
import { ApiError } from "@/infrastructure/http";
import { withAuth } from "@/shared/lib/with-auth";
import { useAuthStore } from "@/shared/stores/auth-store";

const SESSION: AuthSession = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
  user: { id: "user-1", email: "a@b.com", full_name: "A", role: "ADMIN" },
};

function jsonResponse(body: unknown, init?: { status?: number }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": "application/json" },
  });
}

function problemResponse(code: string, status: number): Response {
  return jsonResponse({ type: `urn:forja:problem:${code}`, title: "Error", status }, { status });
}

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.setState({ session: null, status: "idle" });
});

describe("withAuth", () => {
  it("executa a chamada com o token atual", async () => {
    useAuthStore.getState().setSession(SESSION);
    const request = vi.fn(async (token: string) => token);
    vi.stubGlobal("fetch", vi.fn());

    const result = await withAuth(request);

    expect(result).toBe("access-1");
    expect(request).toHaveBeenCalledWith("access-1");
  });

  it("rotaciona a sessão e repete quando o token expira", async () => {
    useAuthStore.getState().setSession(SESSION);

    const tokens = {
      access_token: "access-2",
      refresh_token: "refresh-2",
      token_type: "bearer",
      expires_in: 900,
    };

    const request = vi
      .fn<(token: string) => Promise<string>>()
      .mockRejectedValueOnce(
        new ApiError({
          type: "urn:forja:problem:token_expired",
          title: "Unauthorized",
          status: 401,
        }),
      )
      .mockResolvedValueOnce("access-2");

    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(tokens));
    vi.stubGlobal("fetch", fetchMock);

    const result = await withAuth(request);

    expect(result).toBe("access-2");
    expect(request).toHaveBeenCalledTimes(2);
    expect(useAuthStore.getState().session?.access_token).toBe("access-2");
  });

  it("propaga o erro original quando não é expiração", async () => {
    useAuthStore.getState().setSession(SESSION);
    const error = new ApiError({
      type: "urn:forja:problem:insufficient_credit",
      title: "Conflict",
      status: 409,
    });
    const request = vi.fn().mockRejectedValue(error);
    vi.stubGlobal("fetch", vi.fn());

    await expect(withAuth(request)).rejects.toMatchObject({ status: 409 });
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("lança unauthenticated sem sessão", async () => {
    useAuthStore.setState({ session: null, status: "unauthenticated" });
    vi.stubGlobal("fetch", vi.fn());

    await expect(withAuth(vi.fn())).rejects.toThrow("unauthenticated");
  });
});
