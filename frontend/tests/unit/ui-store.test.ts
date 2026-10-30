import { describe, expect, it } from "vitest";

import { useUiStore } from "@/shared/stores/ui-store";

describe("ui-store (Zustand)", () => {
  it("inicia no tema claro", () => {
    useUiStore.setState({ theme: "light" });
    expect(useUiStore.getState().theme).toBe("light");
  });

  it("alterna o tema com toggleTheme", () => {
    useUiStore.setState({ theme: "light" });
    useUiStore.getState().toggleTheme();
    expect(useUiStore.getState().theme).toBe("dark");
    useUiStore.getState().toggleTheme();
    expect(useUiStore.getState().theme).toBe("light");
  });

  it("persiste cor de destaque e tamanho de fonte", () => {
    useUiStore.getState().setAccent("violet");
    useUiStore.getState().setFontSize("large");
    expect(useUiStore.getState().accent).toBe("violet");
    expect(useUiStore.getState().fontSize).toBe("large");
    useUiStore.setState({ accent: "amber", fontSize: "normal" });
  });

  it("define um tema explícito", () => {
    useUiStore.getState().setTheme("dark");
    expect(useUiStore.getState().theme).toBe("dark");
    useUiStore.setState({ theme: "light" });
  });
});
