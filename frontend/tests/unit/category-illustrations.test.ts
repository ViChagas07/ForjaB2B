import { describe, expect, it } from "vitest";

import { categoryIllustration } from "@/features/home/category-illustrations";

describe("ilustração por nome de categoria", () => {
  it("casa os quatro nomes das fotos de categoria", () => {
    expect(categoryIllustration("EPIs")).toBe("/catalog/illustrations/EPIs.jpg");
    expect(categoryIllustration("Ferramentas Elétricas")).toBe(
      "/catalog/illustrations/Ferramentas Elétricas.jpg",
    );
    expect(categoryIllustration("Maquinas e Ferramentas")).toBe(
      "/catalog/illustrations/Máquinas e Ferramentas.jpg",
    );
    expect(categoryIllustration("Máquinas Estacionárias")).toBe(
      "/catalog/illustrations/Máquinas Estacionárias.jpg",
    );
  });

  it("ignora caixa e acentos vindos da API", () => {
    expect(categoryIllustration("EPIS")).toBe("/catalog/illustrations/EPIs.jpg");
    expect(categoryIllustration("ferramentas eletricas")).toBe(
      "/catalog/illustrations/Ferramentas Elétricas.jpg",
    );
    expect(categoryIllustration("MÁQUINAS E FERRAMENTAS")).toBe(
      "/catalog/illustrations/Máquinas e Ferramentas.jpg",
    );
  });

  it("retorna undefined para categoria sem foto", () => {
    expect(categoryIllustration("Parafusos")).toBeUndefined();
    expect(categoryIllustration("")).toBeUndefined();
  });
});
