import { describe, expect, it } from "vitest";

import { splitHighlight } from "@/shared/components/search-combobox/highlight-match";

function rendered(parts: ReturnType<typeof splitHighlight>): string {
  return parts.map((part) => (part.bold ? `[${part.text}]` : part.text)).join("");
}

describe("splitHighlight", () => {
  it("destaca o prefixo sem diferenciar maiúsculas", () => {
    const parts = splitHighlight("Capacete JSP", "cap");
    expect(rendered(parts)).toBe("[Cap]acete JSP");
    expect(parts[0]?.bold).toBe(true);
  });

  it("ignora acentos no texto e na consulta", () => {
    expect(rendered(splitHighlight("Óculos de Proteção", "oculos"))).toBe("[Óculos] de Proteção");
    expect(rendered(splitHighlight("Óculos de Proteção", "protecao"))).toBe("Óculos de [Proteção]");
    expect(rendered(splitHighlight("Luva Nitrílica", "nitrilica"))).toBe("Luva [Nitrílica]");
  });

  it("destaca no meio do texto (ex.: marca dentro do nome)", () => {
    expect(rendered(splitHighlight("Luva 3M Seguranca", "3m"))).toBe("Luva [3M] Seguranca");
  });

  it("mantém o texto inteiro quando não há correspondência", () => {
    const parts = splitHighlight("Botina Couro", "cap");
    expect(parts).toEqual([{ text: "Botina Couro", bold: false }]);
  });

  it("consulta vazia ou só espaços não destaca nada", () => {
    expect(splitHighlight("Botina Couro", "")).toEqual([{ text: "Botina Couro", bold: false }]);
    expect(splitHighlight("Botina Couro", "   ")).toEqual([{ text: "Botina Couro", bold: false }]);
  });

  it("funciona com árabe (sem diacríticos) preservando o texto original", () => {
    expect(rendered(splitHighlight("قفازات عمل", "قفا"))).toBe("[قفا]زات عمل");
  });

  it("recorta corretamente após caracteres que mudam de tamanho na decomposição", () => {
    // "á" decompõe em 2 codepoints; os índices precisam voltar ao original.
    expect(rendered(splitHighlight("Água e Óleo", "gua"))).toBe("Á[gua] e Óleo");
  });

  it("partes vazias nas pontas são removidas", () => {
    const parts = splitHighlight("Cap", "cap");
    expect(parts).toEqual([{ text: "Cap", bold: true }]);
  });
});
