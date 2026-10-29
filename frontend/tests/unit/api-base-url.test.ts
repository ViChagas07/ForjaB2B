import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "@/infrastructure/http/config";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("base URL da API", () => {
  it("no navegador usa o caminho relativo same-origin", () => {
    vi.stubGlobal("window", {});
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com");

    expect(getApiBaseUrl()).toBe("/api/v1");
  });

  it("no servidor usa BACKEND_URL absoluta sem passar pelo rewrite", () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com/");

    expect(getApiBaseUrl()).toBe("https://forjab2b.onrender.com/api/v1");
  });

  it("no servidor sem BACKEND_URL em producao falha com erro claro", () => {
    vi.stubEnv("BACKEND_URL", "");
    vi.stubEnv("NODE_ENV", "production");

    expect(() => getApiBaseUrl()).toThrow(/BACKEND_URL/);
  });

  it("no servidor em desenvolvimento usa o backend local", () => {
    vi.stubEnv("BACKEND_URL", "");
    vi.stubEnv("NODE_ENV", "development");

    expect(getApiBaseUrl()).toBe("http://localhost:8000/api/v1");
  });
});
