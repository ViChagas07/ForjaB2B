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

  it("define um tema explícito", () => {
    useUiStore.getState().setTheme("dark");
    expect(useUiStore.getState().theme).toBe("dark");
    useUiStore.setState({ theme: "light" });
  });
});
