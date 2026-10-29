import { afterEach, describe, expect, it, vi } from "vitest";

type Rewrite = { source: string; destination: string };
type NextConfigWithRewrites = {
  trailingSlash: boolean;
  rewrites: () => Promise<Rewrite[]>;
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("rewrites do proxy same-origin", () => {
  it("mapeia /api/v1 e /static para BACKEND_URL (somente servidor)", async () => {
    vi.stubEnv("BACKEND_URL", "https://forjab2b.onrender.com/");

    const module = (await import("../../next.config.mjs")) as {
      default: NextConfigWithRewrites;
    };
    const rewrites = await module.default.rewrites();

    expect(module.default.trailingSlash).toBe(false);
    expect(rewrites).toContainEqual({
      source: "/api/v1/:path*",
      destination: "https://forjab2b.onrender.com/api/v1/:path*",
    });
    expect(rewrites).toContainEqual({
      source: "/static/:path*",
      destination: "https://forjab2b.onrender.com/static/:path*",
    });
  });
});
