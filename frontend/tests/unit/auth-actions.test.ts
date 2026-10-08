import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthSession } from "@/core/domain/auth";
import { login, logout, refreshSession } from "@/shared/stores/auth-actions";
import { useAuthStore } from "@/shared/stores/auth-store";

const SESSION: AuthSession = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
  user: { id: "user-1", email: "admin@empresa.com", full_name: "Admin", role: "ADMIN" },
};

function jsonResponse(body: unknown, init?: { status?: number; contentType?: string }): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: { "content-type": init?.contentType ?? "application/json" },
  });
}

function problemResponse(code: string, status: number): Response {
  return jsonResponse(
    { type: `urn:forja:problem:${code}`, title: "Error", status },
    { status, contentType: "application/problem+json" },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.setState({ session: null, status: "idle" });
});

describe("login", () => {
  it("faz login com sucesso e atualiza a store", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(SESSION)));

    const session = await login("admin@empresa.com", "senha");

    expect(session).toEqual(SESSION);
    expect(useAuthStore.getState().session).toEqual(SESSION);
    expect(useAuthStore.getState().status).toBe("authenticated");
  });

  it("propaga credenciais inválidas sem alterar a store", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(problemResponse("invalid_credentials", 401)));

    await expect(login("admin@empresa.com", "errada")).rejects.toMatchObject({
      code: "urn:forja:problem:invalid_credentials",
      status: 401,
    });
    expect(useAuthStore.getState().session).toBeNull();
  });
});

describe("logout", () => {
  it("revoga o refresh token e limpa a sessão", async () => {
    useAuthStore.getState().setSession(SESSION);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await logout();

    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().status).toBe("unauthenticated");
  });

  it("limpa a sessão local mesmo se a API falhar", async () => {
    useAuthStore.getState().setSession(SESSION);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    await logout();

    expect(useAuthStore.getState().session).toBeNull();
  });
});

describe("refreshSession", () => {
  it("rotaciona tokens e preserva o perfil", async () => {
    useAuthStore.getState().setSession(SESSION);
    const tokens = {
      access_token: "access-2",
      refresh_token: "refresh-2",
      token_type: "bearer",
      expires_in: 900,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(tokens)));

    const next = await refreshSession();

    expect(next.access_token).toBe("access-2");
    expect(next.refresh_token).toBe("refresh-2");
    expect(next.user).toEqual(SESSION.user);
    expect(useAuthStore.getState().session?.access_token).toBe("access-2");
  });

  it("limpa a sessão quando o refresh é rejeitado", async () => {
    useAuthStore.getState().setSession(SESSION);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(problemResponse("invalid_refresh_token", 401)),
    );

    await expect(refreshSession()).rejects.toMatchObject({
      code: "urn:forja:problem:invalid_refresh_token",
    });
    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().status).toBe("unauthenticated");
  });
});
