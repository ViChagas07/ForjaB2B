import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const LOCALES = ["pt-BR", "en", "es", "fr", "de", "it", "ar", "ja", "ko", "ru", "zh-CN"] as const;

function readMessages(locale: string): Record<string, unknown> {
  return JSON.parse(
    readFileSync(join(process.cwd(), "messages", `${locale}.json`), "utf-8"),
  ) as Record<string, unknown>;
}

function leafKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return [prefix];
  }
  return Object.entries(value).flatMap(([key, child]) =>
    leafKeys(child, prefix ? `${prefix}.${key}` : key),
  );
}

function pick(root: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((current, part) => {
    if (typeof current !== "object" || current === null) return undefined;
    return (current as Record<string, unknown>)[part];
  }, root);
}

describe("i18n de cupons", () => {
  it("tem todas as chaves de cupom nos 11 locales", () => {
    const pt = readMessages("pt-BR");
    const required = [
      ...leafKeys(pick(pt, "admin.coupons"), "admin.coupons"),
      ...leafKeys(pick(pt, "ordering.coupon"), "ordering.coupon"),
    ];
    expect(required.length).toBeGreaterThan(20);

    for (const locale of LOCALES) {
      const messages = readMessages(locale);
      for (const key of required) {
        const value = pick(messages, key);
        expect(typeof value, `${locale}:${key}`).toBe("string");
        expect(String(value).trim(), `${locale}:${key}`).not.toBe("");
      }
    }
  });
});
