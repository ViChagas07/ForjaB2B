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

/** Chaves que podem ser idênticas ao pt-BR em qualquer idioma. */
const ALLOWED_IDENTICAL_KEYS = new Set([
  "appName",
  "homeTitle",
  "onboarding.cnpjPlaceholder",
  "onboarding.adminCpfPlaceholder",
  "catalog.weightKg", // "{weight} kg" é numérico + unidade
  // Siglas, códigos e nomes de meios de pagamento (não se traduzem)
  "catalog.sku",
  "catalog.sortSku",
  "catalog.ncm",
  "catalog.epi",
  "catalog.epiYes",
  "company.cnpj",
  "onboarding.cnpjLabel",
  "ordering.pix",
  "ordering.boleto",
  // Endereço de contato da política de privacidade (idêntico em todos os idiomas)
  "privacy.contactEmail",
  // Versão do documento da política (numérica, não se traduz)
  "privacy.version",
  // Termos/cognatos idênticos em pelo menos um dos idiomas
  "catalog.fallback",
  "catalog.brand",
  "catalog.filterBrand",
  "catalog.category",
  "catalog.filterCategory",
  "catalog.previous",
  "catalog.weight",
  "catalog.sortName",
  "catalog.sortAsc",
  "catalog.sortDesc",
  "cart.subtotal",
  "company.status",
  "credit.limit",
  "credit.entryType",
  "credit.used",
  "credit.date",
  "languageLabel",
  "ordering.cancel",
  "ordering.status",
  "ordering.statusCancelled",
  "ordering.subtotal",
  "ordering.total",
]);

/** Valores legítimos que coincidem com o pt-BR em um idioma específico. */
const ALLOWED_IDENTICAL_VALUES: Record<string, Set<string>> = {
  es: new Set([
    "Catálogo",
    "Ordenar por",
    "Página {page} de {pages}",
    "{count} resultados",
    "CA válido",
    "CA ausente",
    "Mínimo de {qty}",
    "Finalizar pedido",
    "Confirmar pedido",
    "Confirmando…",
    "Crédito insuficiente",
    "Pedido realizado",
    "Ver pedido",
    "Cancelar pedido",
    "Pedido cancelado.",
    "Crédito",
    // Dropdown de busca: "Resultados populares para {q}" é cognato exato em es.
    "Resultados populares para “{q}”",
  ]),
  fr: new Set(["E-mail", "ou"]),
  it: new Set(["E-mail", "Nome completo"]),
};

function isAllowedIdentical(locale: string, key: string, value: string): boolean {
  // O painel de administracao permanece em portugues por decisao do projeto.
  if (key.startsWith("admin.")) return true;
  if (ALLOWED_IDENTICAL_KEYS.has(key)) return true;
  return ALLOWED_IDENTICAL_VALUES[locale]?.has(value) ?? false;
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

    const referenceFile = `${BASE_LOCALE}.json`;
    expect(files).toContain(referenceFile);

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
        expect(
          localizedPlaceholders,
          `placeholders divergentes em ${file} para chave ${key}: esperado ${placeholders.join(", ")}, encontrado ${localizedPlaceholders.join(", ")}`,
        ).toEqual(placeholders);
      }
    }
  });

  it("não mantém texto do pt-BR sem tradução em outros idiomas", () => {
    const baseValues = readValues(`${BASE_LOCALE}.json`);
    const suspectReport: Array<{ file: string; key: string; value: string }> = [];

    for (const file of EXPECTED_FILES) {
      if (file === `${BASE_LOCALE}.json`) continue;
      const locale = file.replace(/\.json$/, "");
      const values = readValues(file);
      for (const [key, baseValue] of Object.entries(baseValues)) {
        const localizedValue = values[key];
        if (localizedValue === baseValue && !isAllowedIdentical(locale, key, baseValue)) {
          suspectReport.push({ file, key, value: baseValue });
        }
      }
    }

    if (suspectReport.length > 0) {
      console.log("\n=== CHAVES SEM TRADUÇÃO (idênticas ao pt-BR) ===");
      for (const entry of suspectReport) {
        console.log(`${entry.file} | ${entry.key} = "${entry.value}"`);
      }
      console.log(`Total: ${suspectReport.length} chaves\n`);
    }

    expect(
      suspectReport,
      `chaves sem tradução: ${suspectReport.map((e) => `${e.file}:${e.key}`).join(", ")}`,
    ).toEqual([]);
  });
});
