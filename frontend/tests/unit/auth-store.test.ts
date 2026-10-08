import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthSession } from "@/core/domain/auth";
import { useAuthStore } from "@/shared/stores/auth-store";

const SESSION: AuthSession = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
  user: { id: "user-1", email: "admin@empresa.com", full_name: "Admin", role: "ADMIN" },
};

const STORAGE_KEY = "forja-auth-session";

function mockLocalStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    removeItem: (key: string) => {
      map.delete(key);
    },
    _dump: () => Object.fromEntries(map),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.setState({ session: null, status: "idle" });
});

describe("auth-store (Zustand)", () => {
  it("começa idle sem sessão", () => {
    expect(useAuthStore.getState().status).toBe("idle");
    expect(useAuthStore.getState().session).toBeNull();
  });

  it("setSession define a sessão e persiste", () => {
    const storage = mockLocalStorage();
    vi.stubGlobal("window", { localStorage: storage });

    useAuthStore.getState().setSession(SESSION);

    expect(useAuthStore.getState().session).toEqual(SESSION);
    expect(useAuthStore.getState().status).toBe("authenticated");
    expect(storage._dump()[STORAGE_KEY]).toBe(JSON.stringify(SESSION));
  });

  it("clearSession limpa a sessão e o storage", () => {
    const storage = mockLocalStorage();
    vi.stubGlobal("window", { localStorage: storage });
    useAuthStore.getState().setSession(SESSION);

    useAuthStore.getState().clearSession();

    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().status).toBe("unauthenticated");
    expect(storage._dump()[STORAGE_KEY]).toBeUndefined();
  });

  it("hydrate carrega sessão persistida", () => {
    const storage = mockLocalStorage();
    storage.setItem(STORAGE_KEY, JSON.stringify(SESSION));
    vi.stubGlobal("window", { localStorage: storage });

    useAuthStore.getState().hydrate();

    expect(useAuthStore.getState().session).toEqual(SESSION);
    expect(useAuthStore.getState().status).toBe("authenticated");
  });

  it("hydrate sem sessão persistida vira unauthenticated", () => {
    const storage = mockLocalStorage();
    vi.stubGlobal("window", { localStorage: storage });

    useAuthStore.getState().hydrate();

    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().status).toBe("unauthenticated");
  });

  it("ignora storage corrompido no hydrate", () => {
    const storage = mockLocalStorage();
    storage.setItem(STORAGE_KEY, "{ not valid json");
    vi.stubGlobal("window", { localStorage: storage });

    useAuthStore.getState().hydrate();

    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().status).toBe("unauthenticated");
  });
});
