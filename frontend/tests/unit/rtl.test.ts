import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

import { directionForLocale, isRtlLocale, locales, rtlLocales } from "@/i18n/locales";

const ROOT = process.cwd();

/** Exceções documentadas: centralização absoluta (simétrica) e animações do Radix. */
const ALLOWED_TOKENS = new Set(["left-[50%]"]);

const PHYSICAL_PATTERNS = [
  /(?<![\w:-])(?:[a-z0-9]+:)*(?:ml|mr|pl|pr|left|right|text-left|text-right|float-left|float-right|border-l|border-r|rounded-l|rounded-r)-[A-Za-z0-9[\]\.\-/%]+/g,
  /(?<![\w:])-(?:[a-z0-9]+:)?(?:ml|mr|pl|pr|left|right)-[A-Za-z0-9[\]\.\-/%]+/g,
];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "admin" || entry.name === "node_modules" || entry.name === ".next") {
        continue;
      }
      out.push(...walk(full));
    } else if (entry.name.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

function physicalClassViolations(): string[] {
  const violations: string[] = [];
  for (const dir of ["app", "features", "shared"]) {
    for (const file of walk(join(ROOT, dir))) {
      const content = readFileSync(file, "utf-8");
      for (const pattern of PHYSICAL_PATTERNS) {
        for (const match of content.matchAll(pattern)) {
          if (!ALLOWED_TOKENS.has(match[0])) {
            violations.push(`${relative(ROOT, file)}: ${match[0]}`);
          }
        }
      }
    }
  }
  return violations;
}

describe("RTL", () => {
  it("deriva a direção de uma única lista RTL", () => {
    expect([...rtlLocales]).toEqual(["ar"]);
    for (const locale of locales) {
      expect(directionForLocale(locale), locale).toBe(locale === "ar" ? "rtl" : "ltr");
      expect(isRtlLocale(locale), locale).toBe(locale === "ar");
    }
  });

  it("não usa classes físicas nas telas do cliente", () => {
    const violations = physicalClassViolations();
    expect(violations, violations.join("\n")).toEqual([]);
  });

  it("tem pilhas de fonte para as escritas presentes", () => {
    const tailwind = readFileSync(join(ROOT, "tailwind.config.ts"), "utf-8");
    for (const font of [
      "Noto Sans",
      "Noto Sans CJK SC",
      "Noto Sans JP",
      "Noto Sans KR",
      "Noto Sans Arabic",
    ]) {
      expect(tailwind, font).toContain(font);
    }
  });
});
