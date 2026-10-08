import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const MESSAGES_DIR = join(process.cwd(), "messages");

const EXPECTED_FILES = ["ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt-BR", "ru", "zh-CN"]
  .map((locale) => `${locale}.json`)
  .sort();

function flattenKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }

  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const full = prefix ? `${prefix}.${key}` : key;
    return flattenKeys(child, full);
  });
}

function readKeys(file: string): string[] {
  const raw = readFileSync(join(MESSAGES_DIR, file), "utf-8");
  return flattenKeys(JSON.parse(raw) as unknown).sort();
}

describe("i18n message parity", () => {
  it("contém exatamente os 11 locales esperados", () => {
    const files = readdirSync(MESSAGES_DIR)
      .filter((f) => f.endsWith(".json"))
      .sort();
    expect(files).toEqual(EXPECTED_FILES);
  });

  it("mantém conjuntos de chaves idênticos em todos os locales", () => {
    const files = readdirSync(MESSAGES_DIR)
      .filter((f) => f.endsWith(".json"))
      .sort();

    const referenceFile = files[0];
    expect(referenceFile).toBeDefined();
    if (!referenceFile) {
      throw new Error("nenhum arquivo de mensagem encontrado");
    }

    const referenceKeys = readKeys(referenceFile);
    expect(referenceKeys.length).toBeGreaterThan(0);

    for (const file of files) {
      expect(readKeys(file), `chaves divergentes em ${file}`).toEqual(referenceKeys);
    }
  });
});
