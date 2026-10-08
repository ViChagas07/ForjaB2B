import { describe, expect, it } from "vitest";

import { isValidCnpj, isValidCpf, normalizeCnpj, normalizeCpf } from "@/core/domain";

describe("normalizeCnpj / isValidCnpj", () => {
  it("remove máscara mantendo apenas dígitos", () => {
    expect(normalizeCnpj("11.222.333/0001-81")).toBe("11222333000181");
    expect(normalizeCnpj("  11.222.333/0001-81 ")).toBe("11222333000181");
  });

  it("aceita CNPJs válidos", () => {
    expect(isValidCnpj("11222333000181")).toBe(true);
    expect(isValidCnpj("11.222.333/0001-81")).toBe(true);
    expect(isValidCnpj("11444777000161")).toBe(true);
  });

  it("rejeita dígito verificador errado", () => {
    expect(isValidCnpj("11222333000182")).toBe(false);
    expect(isValidCnpj("11222333000180")).toBe(false);
  });

  it("rejeita sequências repetidas e tamanhos inválidos", () => {
    expect(isValidCnpj("00000000000000")).toBe(false);
    expect(isValidCnpj("11111111111111")).toBe(false);
    expect(isValidCnpj("123")).toBe(false);
    expect(isValidCnpj("")).toBe(false);
  });
});

describe("normalizeCpf / isValidCpf", () => {
  it("remove máscara mantendo apenas dígitos", () => {
    expect(normalizeCpf("529.982.247-25")).toBe("52998224725");
  });

  it("aceita CPFs válidos", () => {
    expect(isValidCpf("52998224725")).toBe(true);
    expect(isValidCpf("529.982.247-25")).toBe(true);
  });

  it("rejeita dígito verificador errado e sequências repetidas", () => {
    expect(isValidCpf("52998224726")).toBe(false);
    expect(isValidCpf("00000000000")).toBe(false);
    expect(isValidCpf("11111111111")).toBe(false);
  });

  it("rejeita tamanhos inválidos", () => {
    expect(isValidCpf("123")).toBe(false);
    expect(isValidCpf("")).toBe(false);
  });
});
