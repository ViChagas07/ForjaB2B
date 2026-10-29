import { describe, expect, it } from "vitest";

import { displayCategoryName } from "@/shared/lib/category-display";

describe("displayCategoryName", () => {
  it("corrige o nome legado sem acento", () => {
    expect(displayCategoryName("Maquinas e Ferramentas")).toBe("Máquinas e Ferramentas");
    expect(displayCategoryName("MAQUINAS E FERRAMENTAS")).toBe("Máquinas e Ferramentas");
  });

  it("preserva nomes que ja estao corretos", () => {
    expect(displayCategoryName("Máquinas e Ferramentas")).toBe("Máquinas e Ferramentas");
    expect(displayCategoryName("EPIs")).toBe("EPIs");
  });
});
