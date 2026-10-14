import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const MESSAGES_DIR = join(process.cwd(), "messages");

const EXPECTED_FILES = ["ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt-BR", "ru", "zh-CN"]
  .map((locale) => `${locale}.json`)
  .sort();

const BASE_LOCALE = "pt-BR";

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

function readValues(file: string): Record<string, string> {
  const raw = readFileSync(join(MESSAGES_DIR, file), "utf-8");
  const obj = JSON.parse(raw) as Record<string, unknown>;
  const result: Record<string, string> = {};

  function flatten(obj: Record<string, unknown>, prefix = "") {
    for (const [key, value] of Object.entries(obj)) {
      const full = prefix ? `${prefix}.${key}` : key;
      if (typeof value === "string") {
        result[full] = value;
      } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
        flatten(value as Record<string, unknown>, full);
      }
    }
  }
  flatten(obj);
  return result;
}

function hasPlaceholders(value: string): boolean {
  return /\{[^}]+\}/.test(value);
}

function extractPlaceholders(value: string): string[] {
  const matches = value.match(/\{[^}]+\}/g);
  return matches ? matches.sort() : [];
}

function isLikelyProperNounOrNumber(value: string): boolean {
  // Proper nouns (capitalized words), acronyms (all caps), numbers, units, codes
  // SKU-like: EPI-XXX, numbers with units (20V, 850W, 100L, 7 1/4, 15T, 2cv)
  // URLs, email-like
  if (/^[A-Z]{2,}$/.test(value)) return true; // Acronyms
  if (/^[A-Z][a-z]+([ ][A-Z][a-z]+)*$/.test(value)) return true; // Proper nouns
  if (/^\d+(\.\d+)?\s*[A-Za-zª°%]+$/.test(value)) return true; // Numbers with units
  if (/^\d+(\.\d+)?$/.test(value)) return true; // Pure numbers
  if (/^https?:\/\//.test(value)) return true; // URLs
  if (/^[^@]+@[^@]+\.[^@]+$/.test(value)) return true; // Emails
  if (/^[A-Z]{2,}-\d+$/.test(value)) return true; // SKU-like
  if (/^\d+(\s+\d+\/\d+)?[A-Za-z]+$/.test(value)) return true; // Complex numbers like 7 1/4
  return false;
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

  it("não tem valores vazios em nenhum locale", () => {
    for (const file of EXPECTED_FILES) {
      const values = readValues(file);
      const emptyKeys = Object.entries(values)
        .filter(([, v]) => v.trim() === "")
        .map(([k]) => k);
      expect(emptyKeys, `valores vazios em ${file}: ${emptyKeys.join(", ")}`).toEqual([]);
    }
  });

  it("preserva placeholders e marcações ICU em todos os locales", () => {
    const baseValues = readValues(`${BASE_LOCALE}.json`);
    const baseKeysWithPlaceholders = Object.entries(baseValues)
      .filter(([, v]) => hasPlaceholders(v))
      .map(([k, v]) => ({ key: k, placeholders: extractPlaceholders(v) }));

    for (const file of EXPECTED_FILES) {
      if (file === `${BASE_LOCALE}.json`) continue;
      const values = readValues(file);
      for (const { key, placeholders } of baseKeysWithPlaceholders) {
        const localizedValue = values[key];
        expect(localizedValue, `chave ${key} ausente em ${file}`).toBeDefined();
        if (!localizedValue) continue;
        const localizedPlaceholders = extractPlaceholders(localizedValue);
        expect(localizedPlaceholders, `placeholders divergentes em ${file} para chave ${key}: esperado ${placeholders.join(", ")}, encontrado ${localizedPlaceholders.join(", ")}`).toEqual(placeholders);
      }
    }
  });

  it("reporta chaves suspeitas: valor idêntico ao pt-BR em outro idioma (exceto nomes próprios, siglas, números)", () => {
    const baseValues = readValues(`${BASE_LOCALE}.json`);
    const suspectReport: Array<{ file: string; key: string; value: string }> = [];

    for (const file of EXPECTED_FILES) {
      if (file === `${BASE_LOCALE}.json`) continue;
      const values = readValues(file);
      for (const [key, baseValue] of Object.entries(baseValues)) {
        const localizedValue = values[key];
        if (localizedValue === baseValue && !isLikelyProperNounOrNumber(baseValue)) {
          suspectReport.push({ file, key, value: baseValue });
        }
      }
    }

    // Log the report for manual review
    if (suspectReport.length > 0) {
      console.log("\n=== CHAVES SUSPEITAS (idênticas ao pt-BR, exceto nomes próprios/siglas/números) ===");
      for (const entry of suspectReport) {
        console.log(`${entry.file} | ${entry.key} = "${entry.value}"`);
      }
      console.log(`Total: ${suspectReport.length} chaves suspeitas\n`);
    }

    // This test passes but logs the report; we don't fail on suspects
    expect(true).toBe(true);
  });
});
