import { describe, expect, it } from "vitest";

import { buildContentSecurityPolicy, generateNonce } from "@/shared/security/csp";

describe("CSP do frontend", () => {
  const nonce = "bm9uY2UtZGUtdGVzdGU=";

  it("usa nonce e strict-dynamic sem unsafe-inline em scripts", () => {
    const csp = buildContentSecurityPolicy({
      nonce,
      apiUrl: "https://api.forja.example",
      isProduction: true,
    });

    expect(csp).toContain(`script-src 'nonce-${nonce}' 'strict-dynamic'`);
    expect(csp).not.toMatch(/script-src[^;]*unsafe-inline/);
    expect(csp).not.toMatch(/script-src[^;]*unsafe-eval/);
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
  });

  it("limita connect-src e img-src a origem da API", () => {
    const csp = buildContentSecurityPolicy({
      nonce,
      apiUrl: "https://api.forja.example/base",
      isProduction: true,
    });

    expect(csp).toContain("connect-src 'self' https://api.forja.example");
    expect(csp).toContain(
      "img-src 'self' data: blob: https://api.forja.example https://lh3.googleusercontent.com",
    );
    expect(csp).not.toContain("*");
  });

  it("sem URL de API (same-origin) limita connect-src e img-src a 'self'", () => {
    const csp = buildContentSecurityPolicy({ nonce, isProduction: true });

    expect(csp).toContain("connect-src 'self'");
    expect(csp).toContain("img-src 'self' data: blob: https://lh3.googleusercontent.com");
    expect(csp).not.toContain("localhost");
  });

  it("permite eval e websocket apenas em desenvolvimento", () => {
    const dev = buildContentSecurityPolicy({
      nonce,
      apiUrl: "http://localhost:8000",
      isProduction: false,
    });
    const prod = buildContentSecurityPolicy({
      nonce,
      apiUrl: "http://localhost:8000",
      isProduction: true,
      isSecure: true,
    });
    const prodHttp = buildContentSecurityPolicy({
      nonce,
      apiUrl: "http://localhost:8000",
      isProduction: true,
      isSecure: false,
    });

    expect(dev).toContain("'unsafe-eval'");
    expect(dev).toContain("ws:");
    expect(prod).not.toContain("'unsafe-eval'");
    expect(prod).toContain("upgrade-insecure-requests");
    expect(prodHttp).not.toContain("upgrade-insecure-requests");
  });

  it("gera nonce diferente a cada chamada", () => {
    expect(generateNonce()).not.toBe(generateNonce());
  });
});
