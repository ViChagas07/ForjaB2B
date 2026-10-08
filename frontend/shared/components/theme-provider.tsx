"use client";

import * as React from "react";

import { useUiStore, type Theme } from "@/shared/stores/ui-store";

const STORAGE_KEY = "forja-theme";

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark";
}

/**
 * Aplica o tema (light/dark) no elemento <html> e persiste a preferência.
 * A fonte de verdade é o Zustand (ui-store); este provider apenas sincroniza
 * o DOM (classe `dark` + `color-scheme`) e o localStorage.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useUiStore((s) => s.theme);

  React.useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isTheme(stored)) {
      useUiStore.getState().setTheme(stored);
    } else if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
      useUiStore.getState().setTheme("dark");
    }
  }, []);

  React.useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return <>{children}</>;
}
