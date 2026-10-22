import { readdirSync, readFileSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = process.cwd();

const SCAN_DIRS = ["app", "features", "shared"];

const IGNORED_LINE_PARTS = [
  "className=",
  "aria-hidden",
  "viewBox=",
  " d=\"",
  "fill=\"",
  "xmlns",
  "suppressHydrationWarning",
  "import ",
  "//",
  "/*",
  " *",
  "extends ",
  "React.",
  "HTMLAttributes",
];

const ALLOWED_LITERAL_VALUES = new Set(["−", "+", "BRL", "USD", "EUR", "PIX", "SKU", "CA", "CNPJ", "CPF"]);

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

function isClientFile(path: string): boolean {
  return !path.split(sep).includes("admin");
}

function findViolations(): string[] {
  const violations: string[] = [];
  for (const dir of SCAN_DIRS) {
    for (const file of walk(join(ROOT, dir)).filter(isClientFile)) {
      const lines = readFileSync(file, "utf-8").split("\n");
      lines.forEach((line, index) => {
        if (IGNORED_LINE_PARTS.some((part) => line.includes(part))) {
          return;
        }
        const location = `${relative(ROOT, file)}:${index + 1}`;

        const attr = line.match(/(?:aria-label|placeholder|title|alt)="([^"]+)"/);
        const attrValue = attr?.[1];
        if (attrValue && /[A-Za-zÀ-ÿ]/.test(attrValue) && !ALLOWED_LITERAL_VALUES.has(attrValue)) {
          violations.push(`${location} atributo literal: ${attrValue}`);
        }

        const text = line.match(/>\s*([A-Za-zÀ-ÿ][^<>{}]*?)\s*</);
        const value = text?.[1]?.trim();
        if (value && /[A-Za-zÀ-ÿ]{3,}/.test(value) && !ALLOWED_LITERAL_VALUES.has(value)) {
          violations.push(`${location} texto fora do dicionário: "${value}"`);
        }
      });
    }
  }
  return violations;
}

describe("textos do cliente", () => {
  it("não deixa texto fixo fora dos dicionários nas telas do cliente", () => {
    const violations = findViolations();
    expect(violations, violations.join("\n")).toEqual([]);
  });
});
