import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import middleware from "../../middleware";
import { localeLabels, locales } from "@/i18n/locales";

function request(path: string, init?: { acceptLanguage?: string; cookie?: string }) {
  const headers = new Headers();
  if (init?.acceptLanguage) headers.set("accept-language", init.acceptLanguage);
  if (init?.cookie) headers.set("cookie", init.cookie);
  return new NextRequest(`http://localhost:3000${path}`, { headers });
}

function location(response: Response): string {
  return response.headers.get("location") ?? "";
}

describe("seleção de idioma", () => {
  it("mostra os 11 idiomas pelo nome nativo", () => {
    expect(locales).toHaveLength(11);
    expect(locales.map((code) => localeLabels[code])).toEqual([
      "Português (Brasil)",
      "English",
      "中文（简体）",
      "日本語",
      "한국어",
      "Русский",
      "Español",
      "Deutsch",
      "Français",
      "Italiano",
      "العربية",
    ]);
  });

  it("usa o idioma do navegador na primeira visita (match pelo idioma base)", () => {
    expect(location(middleware(request("/", { acceptLanguage: "fr-CA,fr;q=0.9" })))).toContain("/fr");
    expect(location(middleware(request("/", { acceptLanguage: "en-US,en;q=0.9" })))).toContain("/en");
    expect(location(middleware(request("/", { acceptLanguage: "ar-EG,ar;q=0.9" })))).toContain("/ar");
  });

  it("idioma desconhecido cai em pt-BR", () => {
    expect(location(middleware(request("/", { acceptLanguage: "xx-YY" })))).toContain("/pt-BR");
  });

  it("respeita a preferência persistida em cookie", () => {
    const response = middleware(
      request("/", { acceptLanguage: "en-US", cookie: "NEXT_LOCALE=ar" }),
    );
    expect(location(response)).toContain("/ar");
  });

  it("prefixa a rota sem idioma e persiste o cookie", () => {
    const response = middleware(request("/catalog", { acceptLanguage: "en-US,en;q=0.9" }));
    expect(location(response)).toContain("/en/catalog");
    expect(response.headers.get("set-cookie") ?? "").toContain("NEXT_LOCALE=en");
  });

  it("mantém a troca de idioma na mesma rota", () => {
    const response = middleware(request("/es/catalog"));
    expect(location(response)).not.toContain("/es/catalog");
    expect(response.headers.get("x-middleware-rewrite") ?? "").toContain("/es/catalog");
    expect(response.headers.get("set-cookie") ?? "").toContain("NEXT_LOCALE=es");
  });
});
